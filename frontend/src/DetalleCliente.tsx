/**
 * Detalle del cliente (§8.3), etapa 5.
 *
 * "Toda la relacion de cobranza con un cliente en una pantalla": los
 * indicadores de §6, sus facturas abiertas con la alerta de cada una y el
 * estado. El historial de gestiones y el registro de una nueva gestion son de
 * la fase 6, cuando exista ar_gestion con datos.
 */
import { useQuery } from "@tanstack/react-query";

import type { Cliente, DetalleCliente as Detalle, Gestion } from "./api/cliente";
import { Chip } from "./componentes/Chip";
import { Cargando, Fallo } from "./componentes/Estados";
import { Explicacion } from "./componentes/Explicacion";
import { RegistrarGestion } from "./componentes/RegistrarGestion";
import { Superficie } from "./componentes/Superficie";
import { dias, fecha, pesos, porcentaje } from "./formato";
import { irA } from "./navegacion";

const MARCADORES: Record<string, string> = {
  M04: "Riesgo de envejecimiento (alguna factura pasa de 90 días)",
  M05: "Riesgo crítico (alguna factura pasa de 150 días)",
};

/** Estados de §12, con el nombre que ve el usuario y no el valor de la base. */
const ESTADOS: Record<string, string> = {
  activa: "Activa",
  gestionada: "Gestionada",
  cerrada_por_pago: "Cerrada por pago",
  cerrada_manual: "Cerrada",
};

const TIPOS: Record<string, string> = {
  llamada: "Llamada",
  correo: "Correo",
  mensaje: "Mensaje",
  visita: "Visita",
  acuerdo: "Acuerdo de pago",
  disputa: "Disputa",
  otra: "Otra",
};

export function DetalleCliente({
  cliente,
  nit,
}: {
  cliente: Cliente;
  nit: string;
}) {
  const detalle = useQuery({
    queryKey: ["cliente", nit],
    queryFn: () => cliente.cliente(nit),
  });

  if (detalle.isPending) return <Cargando que="el cliente" />;
  if (detalle.isError) return <Fallo error={detalle.error} />;

  const d = detalle.data;

  return (
    <div className="mx-auto max-w-[1400px] space-y-entre p-marco">
      <header className="flex flex-wrap items-start justify-between gap-entre">
        <div>
          <button
            type="button"
            onClick={() => irA({ nombre: "gestion" })}
            className="text-menor text-apagado transition-colors duration-estado hover:text-tinta"
          >
            ← Volver a la lista
          </button>
          <h1 className="mt-1 text-titulo font-semibold tracking-tight text-tinta">
            {d.cliente_nombre || d.cliente_nit}
          </h1>
          <p className="text-menor text-tenue">
            NIT {d.cliente_nit} · corte {fecha(d.corte)}
          </p>
        </div>
        <Chip nivel={d.prioridad} texto={d.prioridad_etiqueta} />
      </header>

      <Indicadores detalle={d} />

      {(d.marcadores?.length ?? 0) > 0 && (
        <Superficie titulo="Marcadores de riesgo">
          <ul className="space-y-1 text-base text-apagado">
            {d.marcadores!.map((m) => (
              <li key={m}>
                <span className="font-semibold text-tinta">{m}</span>{" "}
                {MARCADORES[m] ?? "Marcador de riesgo"}
              </li>
            ))}
          </ul>
        </Superficie>
      )}

      <Superficie titulo="Facturas abiertas y alertas">
        <table className="w-full text-base">
          <thead>
            <tr className="border-b border-filete text-menor uppercase tracking-wide text-tenue">
              <th className="py-1.5 text-left font-medium">Factura</th>
              <th className="py-1.5 text-left font-medium">Alerta</th>
              <th className="py-1.5 text-right font-medium">Días</th>
              <th className="py-1.5 pr-3 text-right font-medium">Saldo</th>
              <th className="py-1.5 text-left font-medium">Prioridad</th>
              <th className="py-1.5 text-left font-medium">Estado</th>
              <th className="py-1.5 text-left font-medium">Acción</th>
            </tr>
          </thead>
          <tbody>
            {d.alertas.map((a) => (
              <tr key={a.id} className="border-b border-filete/60 last:border-0">
                <td className="py-2 pr-2 tabular-nums text-tinta">
                  {a.factura || <span className="text-tenue">del cliente</span>}
                </td>
                <td className="py-2 pr-2">
                  <span className="flex items-center gap-1.5">
                    <span className="font-medium text-tinta">{a.codigo}</span>
                    <Explicacion texto={a.explicacion} />
                  </span>
                  <span className="text-menor text-tenue">{a.etiqueta}</span>
                </td>
                <td className="py-2 text-right tabular-nums text-apagado">
                  {dias(a.dias)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums text-tinta">
                  {a.saldo ? pesos(a.saldo) : "—"}
                  {/* Si hubo nota credito, la diferencia contra el ERP tiene
                      que ser explicable en pantalla (C-10). */}
                  {a.credito_aplicado && Number(a.credito_aplicado) > 0 && (
                    <span className="block text-menor text-tenue">
                      bruto {pesos(a.saldo_bruto ?? "0")} − crédito{" "}
                      {pesos(a.credito_aplicado)}
                    </span>
                  )}
                </td>
                <td className="py-2 pl-2">
                  <Chip nivel={a.prioridad} texto={a.prioridad_etiqueta} />
                </td>
                <td className="py-2 pl-2 text-apagado">
                  {ESTADOS[a.estado] ?? a.estado}
                </td>
                <td className="py-2 pl-2 text-apagado">{a.accion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Superficie>

      <RegistrarGestion cliente={cliente} nit={nit} alertas={d.alertas} />

      <Historial gestiones={d.gestiones ?? []} />
    </div>
  );
}

/** Indicadores de §6, con la identidad de C-14 visible en el desglose. */
function Indicadores({ detalle }: { detalle: Detalle }) {
  const cifras = [
    { etiqueta: "Cartera total", valor: pesos(detalle.cartera_total) },
    { etiqueta: "Por vencer", valor: pesos(detalle.por_vencer) },
    { etiqueta: "Vence hoy", valor: pesos(detalle.vence_hoy) },
    { etiqueta: "Vencida", valor: pesos(detalle.vencida), pie: porcentaje(detalle.pct_vencida) },
    { etiqueta: "Más de 90 días", valor: pesos(detalle.mayor_90), pie: porcentaje(detalle.pct_90) },
    { etiqueta: "Más de 150 días", valor: pesos(detalle.mayor_150) },
    { etiqueta: "Factura más antigua", valor: `${detalle.dias_max} d` },
    { etiqueta: "Facturas vencidas", valor: `${detalle.n_vencidas} de ${detalle.n_facturas}` },
  ];

  return (
    <div className="grid grid-cols-2 gap-entre md:grid-cols-4">
      {cifras.map((c) => (
        <Superficie key={c.etiqueta}>
          <p className="text-menor font-medium uppercase tracking-wide text-apagado">
            {c.etiqueta}
          </p>
          <p className="mt-1 text-medio font-semibold tabular-nums text-tinta">
            {c.valor}
          </p>
          {c.pie && (
            <p className="mt-0.5 text-menor tabular-nums text-tenue">
              {c.pie} del total
            </p>
          )}
        </Superficie>
      ))}
    </div>
  );
}

/** Historial de cobranza (§8.3), de lo mas reciente a lo mas antiguo. */
function Historial({ gestiones }: { gestiones: Gestion[] }) {
  if (gestiones.length === 0) {
    return (
      <Superficie titulo="Historial de gestiones">
        <p className="py-4 text-center text-base text-tenue">
          Todavía no se ha registrado ninguna gestión con este cliente.
        </p>
      </Superficie>
    );
  }

  return (
    <Superficie titulo="Historial de gestiones">
      <ol className="space-y-entre">
        {gestiones.map((g) => (
          <li key={g.id} className="border-b border-filete/60 pb-2 last:border-0 last:pb-0">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-medium text-tinta">
                {TIPOS[g.tipo] ?? g.tipo}
              </span>
              {g.factura && (
                <span className="text-menor tabular-nums text-apagado">
                  factura {g.factura}
                </span>
              )}
              <span className="text-menor tabular-nums text-tenue">
                {new Date(g.fecha).toLocaleString("es-CO")} · {g.usuario_id}
              </span>
            </div>
            {g.resultado && <p className="text-base text-apagado">{g.resultado}</p>}
            {g.observacion && (
              <p className="text-menor text-tenue">{g.observacion}</p>
            )}
            {g.compromiso_fecha && g.compromiso_valor && (
              <p className="mt-0.5 text-menor font-medium text-[#2F6B9A]">
                Compromiso: {pesos(g.compromiso_valor)} para{" "}
                {fecha(g.compromiso_fecha)}
              </p>
            )}
          </li>
        ))}
      </ol>
    </Superficie>
  );
}
