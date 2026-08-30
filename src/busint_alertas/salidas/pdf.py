"""Reporte formal en PDF (§9).

Se genera desde HTML y CSS con WeasyPrint, no dibujando el documento a mano.
La razon esta en §5: asi el reporte reutiliza el mismo sistema de diseno que la
pantalla y no hay que mantener dos maquetaciones que acaban divergiendo.

Los datos salen de `salidas.datos`, igual que el Excel y la pantalla. §13 lo
exige: "El PDF y Excel muestran exactamente la misma clasificacion que la
pantalla para el mismo corte".
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from ..core.dinero import porcentaje, presentar
from .datos import Corte

CERO = Decimal("0.00")

HOJA = """
@page {
  size: A4 landscape;
  margin: 14mm 12mm 16mm 12mm;
  @bottom-right {
    content: "Pagina " counter(page) " de " counter(pages);
    font-size: 8pt; color: #9CA3AF;
  }
  @bottom-left {
    content: "BUSINT - Motor de alertas de cartera";
    font-size: 8pt; color: #9CA3AF;
  }
}
body { font-family: "DejaVu Sans", sans-serif; font-size: 8pt; color: #1A1D21; }
h1 { font-size: 16pt; margin: 0 0 2mm 0; }
.sub { color: #6B7280; font-size: 8pt; margin-bottom: 5mm; }
.kpis { display: flex; gap: 3mm; margin-bottom: 5mm; }
.kpi {
  flex: 1; border: 0.4pt solid #E8EAED; border-radius: 3mm; padding: 2.5mm;
}
.kpi .etiqueta { font-size: 7pt; color: #6B7280; text-transform: uppercase; }
.kpi .valor { font-size: 12pt; font-weight: 600; }
.kpi .pie { font-size: 7pt; color: #9CA3AF; }
h2 {
  font-size: 9pt; text-transform: uppercase; letter-spacing: 0.4pt;
  color: #6B7280; margin: 5mm 0 2mm 0;
}
table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; font-size: 7pt; text-transform: uppercase; color: #6B7280;
  border-bottom: 0.6pt solid #E8EAED; padding: 1.2mm 1mm; font-weight: 600;
}
td { padding: 1.2mm 1mm; border-bottom: 0.3pt solid #F0F1F3; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
.chip {
  display: inline-block; border: 0.4pt solid; border-radius: 6pt;
  padding: 0.2mm 1.4mm; font-size: 7pt; font-weight: 600;
}
.barra { height: 3mm; border-radius: 1mm; display: inline-block; }
.nota { color: #9CA3AF; font-size: 7pt; margin-top: 4mm; }
"""

#: Mismos colores de severidad que la pantalla (§7.2).
TINTA = {0: "#2F6B9A", 1: "#B8860B", 2: "#E67E22", 3: "#9B1C1C", 4: "#641220"}


def generar(corte: Corte, limite_alertas: int = 400) -> bytes:
    """Devuelve el PDF del corte.

    `limite_alertas` acota el detalle: un PDF de medio millon de filas no lo
    lee nadie y tarda minutos en generarse. El Excel es la salida de analisis;
    el PDF es el reporte formal. Cuando se recorta, el documento lo dice.
    """
    from weasyprint import CSS, HTML

    html = _documento(corte, limite_alertas)
    return HTML(string=html).write_pdf(stylesheets=[CSS(string=HOJA)])


def _pesos(valor: Decimal | None) -> str:
    if valor is None:
        return "—"
    return f"$ {presentar(valor):,.0f}".replace(",", ".")


def _chip(nivel: int, texto: str) -> str:
    color = TINTA.get(nivel, TINTA[0])
    return (
        f'<span class="chip" style="color:{color};'
        f'background:{color}17;border-color:{color}2B">{escape(texto)}</span>'
    )


def _documento(corte: Corte, limite: int) -> str:
    total = corte.cartera_total
    kpis = (
        ("Cartera total", corte.cartera_total, None),
        ("Por vencer", corte.por_vencer, porcentaje(corte.por_vencer, total)),
        ("Vence hoy", corte.vence_hoy, porcentaje(corte.vence_hoy, total)),
        ("Vencida", corte.vencida, porcentaje(corte.vencida, total)),
        ("Mas de 90 dias", corte.mayor_90, porcentaje(corte.mayor_90, total)),
    )
    tarjetas = "".join(
        f'<div class="kpi"><div class="etiqueta">{escape(e)}</div>'
        f'<div class="valor">{_pesos(v)}</div>'
        f'<div class="pie">{p if p is None else f"{p} % del total"}</div></div>'
        if p is not None else
        f'<div class="kpi"><div class="etiqueta">{escape(e)}</div>'
        f'<div class="valor">{_pesos(v)}</div><div class="pie"></div></div>'
        for e, v, p in kpis
    )

    ancho_max = max(
        (corte.totales_por_bucket.get(b.codigo, CERO) for b in corte.buckets),
        default=CERO,
    ) or Decimal("1")
    filas_aging = "".join(
        f"<tr><td>{escape(b.etiqueta)}</td>"
        f'<td class="num">{_pesos(corte.totales_por_bucket.get(b.codigo, CERO))}</td>'
        f'<td class="num">{corte.facturas_por_bucket.get(b.codigo, 0)}</td>'
        f'<td class="num">{porcentaje(corte.totales_por_bucket.get(b.codigo, CERO), total)} %</td>'
        f'<td><span class="barra" style="background:{b.color};width:'
        f'{float(corte.totales_por_bucket.get(b.codigo, CERO) / ancho_max * 40):.1f}mm"></span></td></tr>'
        for b in corte.buckets
    )

    filas_clientes = "".join(
        f"<tr><td>{escape(c.cliente_nombre or c.cliente_nit)}</td>"
        f"<td>{escape(c.cliente_nit)}</td>"
        f'<td class="num">{_pesos(c.cartera_total)}</td>'
        f'<td class="num">{c.pct_vencida} %</td>'
        f'<td class="num">{c.pct_90} %</td>'
        f'<td class="num">{c.dias_max}</td>'
        f'<td class="num">{c.n_vencidas}</td>'
        f"<td>{_chip(c.prioridad, corte.etiqueta_prioridad(c.prioridad))}</td></tr>"
        for c in corte.clientes[:40]
    )

    mostradas = list(corte.alertas[:limite])
    filas_alertas = "".join(
        f"<tr><td>{escape(a.codigo)}</td>"
        f"<td>{escape(corte.nombre_de(a.cliente_nit) or a.cliente_nit)}</td>"
        f"<td>{escape(a.factura or '—')}</td>"
        f'<td class="num">{a.dias if a.dias is not None else "—"}</td>'
        f'<td class="num">{_pesos(a.saldo)}</td>'
        f"<td>{_chip(a.prioridad, corte.etiqueta_prioridad(a.prioridad))}</td>"
        f"<td>{escape(a.accion)}</td>"
        f"<td>{escape(a.explicacion or '')}</td></tr>"
        for a in mostradas
    )
    recorte = (
        f"<p class='nota'>Se muestran las primeras {limite} alertas de "
        f"{len(corte.alertas)}. El detalle completo esta en la exportacion a Excel.</p>"
        if len(corte.alertas) > limite else ""
    )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Cartera {corte.corte}</title></head>
<body>
  <h1>Cartera al {corte.corte:%d/%m/%Y}</h1>
  <p class="sub">
    Empresa {escape(corte.empresa_id)} ·
    {len(corte.clientes)} clientes · {len(corte.alertas)} alertas ·
    generado {corte.generado:%d/%m/%Y %H:%M} ·
    parametros {escape(corte.version_parametros[:12])}
  </p>

  <div class="kpis">{tarjetas}</div>

  <h2>Antiguedad de cartera</h2>
  <table>
    <thead><tr><th>Rango</th><th class="num">Saldo</th><th class="num">Facturas</th>
    <th class="num">% del total</th><th></th></tr></thead>
    <tbody>{filas_aging}</tbody>
  </table>

  <h2>Clientes que requieren atencion</h2>
  <table>
    <thead><tr><th>Cliente</th><th>NIT</th><th class="num">Cartera</th>
    <th class="num">% vencida</th><th class="num">% &gt;90</th>
    <th class="num">Dias max</th><th class="num">N vencidas</th>
    <th>Prioridad</th></tr></thead>
    <tbody>{filas_clientes}</tbody>
  </table>

  <h2>Detalle de alertas</h2>
  <table>
    <thead><tr><th>Alerta</th><th>Cliente</th><th>Factura</th>
    <th class="num">Dias</th><th class="num">Saldo</th><th>Prioridad</th>
    <th>Accion</th><th>Por que</th></tr></thead>
    <tbody>{filas_alertas}</tbody>
  </table>
  {recorte}
</body></html>"""
