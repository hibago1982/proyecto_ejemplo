"""Catalogo de reglas R01-R06 y alertas A01-A12.

Una regla se declara siempre, tenga o no definida su logica y sus umbrales. Esa
decision es deliberada: una regla declarada pero inactiva aparece en la pantalla
de configuracion como "pendiente de definir" (§7.3), mientras que una regla
ausente del codigo es invisible y se olvida.

Tres motivos pueden dejar una regla inactiva, y el motor los distingue:

  * `sin_logica`  - la Especificacion Funcional v1.0 no define su condicion.
  * `sin_parametros` - la empresa no ha asignado umbral (C-05).
  * `fase_posterior` - depende de datos que aun no existen (C-07, caso de A12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Iterator, Sequence

from ...core.alerta import Explicacion
from ...core.parametros import Parametros
from ...core.tipos import Fase, Prioridad
from .buckets import Bucket
from .datos import Movimiento


class Ambito:
    """Sobre que se evalua una regla."""

    FACTURA = "factura"
    CLIENTE = "cliente"


@dataclass(frozen=True)
class ContextoFactura:
    """Lo que ve una regla de ambito factura."""

    movimiento: Movimiento
    dias: int
    bucket: Bucket
    dias_sin_gestion: int | None = None
    """Dias que lleva la alerta sin gestion. None si es nueva en este corte."""


@dataclass(frozen=True)
class ContextoCliente:
    """Lo que ve una regla de ambito cliente: el perfil agregado ya calculado."""

    cliente_nit: str
    cartera_total: Decimal
    vencida: Decimal
    pct_vencida: Decimal
    mayor_90: Decimal
    pct_90: Decimal
    mayor_150: Decimal
    dias_max: int
    n_vencidas: int


EvaluadorFactura = Callable[[ContextoFactura, Parametros], Explicacion | None]
EvaluadorCliente = Callable[[ContextoCliente, Parametros], Explicacion | None]


@dataclass(frozen=True)
class DefinicionRegla:
    """Una regla del motor y la alerta que emite cuando se cumple."""

    codigo: str
    etiqueta: str
    ambito: str
    prioridad: Prioridad
    accion: str
    alerta: str | None = None
    """Codigo del catalogo de alertas que emite. None si solo marca riesgo (C-04)."""

    marcador: str | None = None
    """Codigo de marcador de riesgo de cliente, para R04 y R05 (C-04)."""

    parametros_requeridos: tuple[str, ...] = ()
    eleva_prioridad: int = 0
    """Niveles que sube la prioridad de la factura cuando la regla se cumple.

    R01 no emite alerta propia: su efecto es agravar la que la factura ya tiene
    por antiguedad. Es la unica regla de §5.4 cuyo efecto es este.
    """

    fase: Fase = Fase.F1_MOTOR
    evaluar: EvaluadorFactura | EvaluadorCliente | None = None
    """None significa que la condicion aun no esta definida en la especificacion."""

    nota: str = ""

    def inactiva_porque(
        self, parametros: Parametros, fase_vigente: Fase
    ) -> str | None:
        """Motivo por el que esta regla no debe evaluarse, o None si procede."""
        if self.evaluar is None:
            return (
                f"Condicion sin definir en la Especificacion Funcional v1.0. {self.nota}".strip()
            )
        if self.fase.value > fase_vigente.value:
            return (
                f"Requiere la fase {self.fase.value}; la fase vigente es "
                f"{fase_vigente.value} (C-07)."
            )
        faltantes = parametros.faltantes(self.parametros_requeridos)
        if faltantes:
            return (
                "La empresa no ha asignado valor a: "
                + ", ".join(faltantes)
                + ". La regla permanece inactiva (C-05)."
            )
        return None


# --------------------------------------------------------------------------
# Evaluadores con condicion definida
# --------------------------------------------------------------------------


def _r01_saldo_alto_vencido(ctx: ContextoFactura, p: Parametros) -> Explicacion | None:
    """R01 - saldo sobre umbral y mas de 30 dias vencida. Eleva la prioridad.

    §5.4 es explicito en las dos condiciones: el umbral monetario por si solo no
    basta, la factura ademas tiene que llevar mas de 30 dias vencida. No emite
    alerta propia; agrava la que ya tiene por antiguedad.
    """
    umbral = p.decimal("umbral_saldo_alto")
    if ctx.movimiento.saldo > umbral and ctx.dias > 30:
        return Explicacion(
            regla="R01",
            motivo=f"saldo de {ctx.movimiento.saldo} con {ctx.dias} dias vencida",
            parametro="umbral_saldo_alto",
            valor_parametro=umbral,
            valor_observado=ctx.movimiento.saldo,
        )
    return None


def _r02_exposicion_alta(ctx: ContextoFactura, p: Parametros) -> Explicacion | None:
    """R02 / A09 - el saldo supera el umbral critico.

    §5.4 no repite la condicion de dias que si lleva R01, asi que aplica a
    cualquier antiguedad, incluida una factura por vencer.
    """
    umbral = p.decimal("umbral_saldo_critico")
    if ctx.movimiento.saldo > umbral:
        return Explicacion(
            regla="R02",
            motivo=f"saldo de {ctx.movimiento.saldo} sobre el umbral critico",
            parametro="umbral_saldo_critico",
            valor_parametro=umbral,
            valor_observado=ctx.movimiento.saldo,
        )
    return None


def _r03_facturas_vencidas(ctx: ContextoCliente, p: Parametros) -> Explicacion | None:
    """R03 / A10 - el cliente acumula N o mas facturas vencidas.

    C-02: §5.4 dice "mas de N" y §7 A10 dice "N o mas". Con N=3 y un cliente de
    3 facturas vencidas una regla disparaba y la otra no. Se adopta el operador
    mayor o igual, criterio de A10, porque A10 es quien genera el identificador.
    """
    umbral = p.entero("n_facturas_vencidas")
    if ctx.n_vencidas >= umbral:
        return Explicacion(
            regla="R03",
            motivo=f"el cliente tiene {ctx.n_vencidas} facturas vencidas",
            parametro="n_facturas_vencidas",
            valor_parametro=umbral,
            valor_observado=ctx.n_vencidas,
        )
    return None


def _r04_envejecimiento(ctx: ContextoCliente, p: Parametros) -> Explicacion | None:
    """R04 - alguna factura del cliente pasa de 90 dias.

    El corte de 90 esta escrito en §5.4 y no es parametrizable, igual que los
    indicadores de §6 que usan el mismo umbral.
    """
    if ctx.dias_max > 90:
        return Explicacion(
            regla="R04",
            motivo=f"su factura mas antigua lleva {ctx.dias_max} dias vencida",
            valor_observado=ctx.dias_max,
        )
    return None


def _r05_riesgo_critico(ctx: ContextoCliente, p: Parametros) -> Explicacion | None:
    """R05 - alguna factura del cliente pasa de 150 dias."""
    if ctx.dias_max > 150:
        return Explicacion(
            regla="R05",
            motivo=f"su factura mas antigua lleva {ctx.dias_max} dias vencida",
            valor_observado=ctx.dias_max,
        )
    return None


def _r06_preventiva(ctx: ContextoFactura, p: Parametros) -> Explicacion | None:
    """R06 / A01 - la factura vence dentro de la ventana preventiva.

    Estrictamente por vencer: el dia del vencimiento lo cubre A02 con prioridad
    Alta, no A01. §7 los separa y §14 lo confirma con T01 y T02.

    C-06: el parametro se llama `dias_preventivos` y no "X", para no confundirlo
    con el `dias_sin_gestion` de A12, que la especificacion tambien llamaba "X".
    """
    dias_preventivos = p.entero("dias_preventivos")
    if -dias_preventivos <= ctx.dias < 0:
        faltan = -ctx.dias
        return Explicacion(
            regla="R06",
            motivo=f"la factura vence en {faltan} dias",
            parametro="dias_preventivos",
            valor_parametro=dias_preventivos,
            valor_observado=faltan,
        )
    return None


def _a12_sin_gestion(ctx: ContextoFactura, p: Parametros) -> Explicacion | None:
    """A12 - la alerta lleva X dias activa sin gestion registrada (§7, §11).

    Solo se evalua desde la fase 6, cuando ar_gestion tiene datos. C-07 lo
    advertia: activarla antes la dispararia siempre, porque ninguna alerta
    tendria gestion contra la cual evaluarse.

    Una alerta nacida en este mismo corte no dispara: `dias_sin_gestion` viene
    en None y no hay desde cuando contar.
    """
    if ctx.dias_sin_gestion is None:
        return None
    umbral = p.entero("dias_sin_gestion")
    if ctx.dias_sin_gestion >= umbral:
        return Explicacion(
            regla="A12",
            motivo=f"lleva {ctx.dias_sin_gestion} dias sin gestion registrada",
            parametro="dias_sin_gestion",
            valor_parametro=umbral,
            valor_observado=ctx.dias_sin_gestion,
        )
    return None


def _a11_concentracion_mayor_90(
    ctx: ContextoCliente, p: Parametros
) -> Explicacion | None:
    """A11 - el porcentaje de cartera a mas de 90 dias supera el umbral.

    C-05: `pct_mayor_90_umbral` no existia entre los parametros administrables
    de §5.4. Se anade aqui; mientras la empresa no le asigne valor, la alerta
    permanece inactiva y el motor no asume ningun porcentaje por defecto.
    """
    umbral = p.decimal("pct_mayor_90_umbral")
    if ctx.pct_90 > umbral:
        return Explicacion(
            regla="A11",
            motivo=f"el {ctx.pct_90}% de su cartera supera los 90 dias",
            parametro="pct_mayor_90_umbral",
            valor_parametro=umbral,
            valor_observado=ctx.pct_90,
        )
    return None


# --------------------------------------------------------------------------
# Catalogo
# --------------------------------------------------------------------------

#: Reglas de §5.4 con sus efectos, y las dos alertas de §7 que no tienen
#: codigo de regla propio.
REGLAS: tuple[DefinicionRegla, ...] = (
    DefinicionRegla(
        codigo="R01",
        etiqueta="Saldo alto en mora",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.INFORMATIVA,
        accion="Priorizar en la gestion del dia",
        alerta=None,
        parametros_requeridos=("umbral_saldo_alto",),
        eleva_prioridad=1,
        evaluar=_r01_saldo_alto_vencido,
        nota="Su efecto es elevar la prioridad, no emitir alerta (§5.4).",
    ),
    DefinicionRegla(
        codigo="R02",
        etiqueta="Alta exposicion",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.ALTA,
        accion="Revisar exposicion",
        alerta="A09",
        parametros_requeridos=("umbral_saldo_critico",),
        evaluar=_r02_exposicion_alta,
    ),
    DefinicionRegla(
        codigo="R03",
        etiqueta="Cliente reincidente",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.ALTA,
        accion="Revisar comportamiento",
        alerta="A10",
        parametros_requeridos=("n_facturas_vencidas",),
        evaluar=_r03_facturas_vencidas,
    ),
    DefinicionRegla(
        codigo="R04",
        etiqueta="Riesgo de envejecimiento",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.MUY_ALTA,
        accion="Revisar condiciones de credito",
        alerta=None,
        marcador="M04",
        evaluar=_r04_envejecimiento,
        nota="C-04: marcador de cliente, no alerta de factura.",
    ),
    DefinicionRegla(
        codigo="R05",
        etiqueta="Riesgo critico",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.CRITICA,
        accion="Evaluar recuperacion",
        alerta=None,
        marcador="M05",
        evaluar=_r05_riesgo_critico,
        nota="C-04: marcador de cliente, no alerta de factura.",
    ),
    DefinicionRegla(
        codigo="R06",
        etiqueta="Proximo vencimiento",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.MEDIA,
        accion="Registrar seguimiento",
        alerta="A01",
        parametros_requeridos=("dias_preventivos",),
        evaluar=_r06_preventiva,
        nota="C-03: prioridad Media, no Informativa.",
    ),
    DefinicionRegla(
        codigo="A11",
        etiqueta="Envejecimiento critico",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.MUY_ALTA,
        accion="Intervencion",
        alerta="A11",
        parametros_requeridos=("pct_mayor_90_umbral",),
        evaluar=_a11_concentracion_mayor_90,
        nota="§7 no le asigna codigo de regla; se usa el de la alerta.",
    ),
    DefinicionRegla(
        codigo="A12",
        etiqueta="Sin gestion",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.ALTA,
        accion="Escalar al responsable",
        alerta="A12",
        parametros_requeridos=("dias_sin_gestion",),
        fase=Fase.F5_GESTION,
        evaluar=_a12_sin_gestion,
        nota="C-07: depende del historial de gestion. No se evalua antes de la "
        "fase 5, porque sin gestiones registradas se disparia siempre.",
    ),
)

#: Catalogo de alertas de §7. A02-A08 las emiten los buckets de §5.2.
ETIQUETAS_ALERTA: dict[str, str] = {
    "A01": "Proximo vencimiento",
    "A02": "Vence hoy",
    "A03": "Mora 1-30",
    "A04": "Mora 31-60",
    "A05": "Mora 61-90",
    "A06": "Mora 91-120",
    "A07": "Mora 121-150",
    "A08": "Mora mayor a 150",
    "A09": "Alta exposicion",
    "A10": "Cliente reincidente",
    "A11": "Envejecimiento critico",
    "A12": "Sin gestion",
}

ETIQUETAS_MARCADOR: dict[str, str] = {
    "M04": "Riesgo de envejecimiento",
    "M05": "Riesgo critico",
}



def reglas_de_ambito(ambito: str) -> Iterator[DefinicionRegla]:
    return (r for r in REGLAS if r.ambito == ambito)
