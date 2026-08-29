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


def _r03_facturas_vencidas(ctx: ContextoCliente, p: Parametros) -> Explicacion | None:
    """R03 / A10 - el cliente acumula N o mas facturas vencidas.

    C-02: §5.4 decia "mas de N" y §7 decia "N o mas". Con N=3 y un cliente de 3
    facturas vencidas una regla disparaba y la otra no. Se adopta el operador
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


def _r06_preventiva(ctx: ContextoFactura, p: Parametros) -> Explicacion | None:
    """R06 / A01 - la factura vence dentro de la ventana preventiva.

    C-06: el parametro se llama `dias_preventivos` y no "X", para no confundirlo
    con el `dias_sin_gestion` de A12, que la especificacion tambien llamaba "X".
    """
    dias_preventivos = p.entero("dias_preventivos")
    if -dias_preventivos <= ctx.dias <= 0:
        faltan = -ctx.dias
        motivo = (
            "la factura vence hoy"
            if faltan == 0
            else f"la factura vence en {faltan} dias"
        )
        return Explicacion(
            regla="R06",
            motivo=motivo,
            parametro="dias_preventivos",
            valor_parametro=dias_preventivos,
            valor_observado=faltan,
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

#: Reglas del motor de cartera.
#:
#: R01, R02, R04 y R05 se declaran con su forma conocida pero sin evaluador: la
#: Especificacion Funcional v1.0 §5.4 no llego a este documento y su condicion
#: exacta no puede inventarla el programador. Al no tener evaluador quedan
#: inactivas y aparecen como pendientes en la configuracion.
REGLAS: tuple[DefinicionRegla, ...] = (
    DefinicionRegla(
        codigo="R01",
        etiqueta="Saldo vencido sobre umbral monetario",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.ALTA,
        accion="Contactar al cliente",
        alerta=None,
        parametros_requeridos=("umbral_monetario_r01",),
        evaluar=None,
        nota="Falta §5.4: sobre que monto compara y que alerta emite.",
    ),
    DefinicionRegla(
        codigo="R02",
        etiqueta="Exposicion del cliente sobre umbral monetario",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.ALTA,
        accion="Escalar a coordinador",
        alerta=None,
        parametros_requeridos=("umbral_monetario_r02",),
        evaluar=None,
        nota="Falta §5.4: la especificacion le asigna un identificador de alerta "
        "que este documento no transcribe.",
    ),
    DefinicionRegla(
        codigo="R03",
        etiqueta="Acumulacion de facturas vencidas",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.ALTA,
        accion="Escalar a coordinador",
        alerta="A10",
        parametros_requeridos=("n_facturas_vencidas",),
        evaluar=_r03_facturas_vencidas,
    ),
    DefinicionRegla(
        codigo="R04",
        etiqueta="Marcador de riesgo por comportamiento de pago",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.MEDIA,
        accion="Revisar condiciones de credito",
        alerta=None,
        marcador="M04",
        evaluar=None,
        nota="C-04: se modela como marcador de cliente, no como alerta de factura. "
        "Falta §5.4 para su condicion.",
    ),
    DefinicionRegla(
        codigo="R05",
        etiqueta="Marcador de riesgo por concentracion de cartera",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.MEDIA,
        accion="Revisar condiciones de credito",
        alerta=None,
        marcador="M05",
        evaluar=None,
        nota="C-04: se modela como marcador de cliente. Falta §5.4 para su condicion.",
    ),
    DefinicionRegla(
        codigo="R06",
        etiqueta="Aviso preventivo de vencimiento",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.MEDIA,
        accion="Recordar al cliente antes del vencimiento",
        alerta="A01",
        parametros_requeridos=("dias_preventivos",),
        evaluar=_r06_preventiva,
    ),
    DefinicionRegla(
        codigo="A11",
        etiqueta="Concentracion de cartera a mas de 90 dias",
        ambito=Ambito.CLIENTE,
        prioridad=Prioridad.CRITICA,
        accion="Escalar a coordinador",
        alerta="A11",
        parametros_requeridos=("pct_mayor_90_umbral",),
        evaluar=_a11_concentracion_mayor_90,
        nota="La especificacion no le asigna codigo de regla; se usa el de la alerta.",
    ),
    DefinicionRegla(
        codigo="A12",
        etiqueta="Factura sin gestion registrada",
        ambito=Ambito.FACTURA,
        prioridad=Prioridad.ALTA,
        accion="Registrar gestion de cobro",
        alerta="A12",
        parametros_requeridos=("dias_sin_gestion",),
        fase=Fase.F5_GESTION,
        evaluar=None,
        nota="C-07: depende del historial de gestion, que no existe antes de la "
        "fase 5. Activarla antes la dispararia siempre.",
    ),
)

#: Etiquetas del catalogo de alertas, para presentacion.
ETIQUETAS_ALERTA: dict[str, str] = {
    "A01": "Proximo a vencer",
    "A10": "Multiples facturas vencidas",
    "A11": "Concentracion en mora mayor a 90 dias",
    "A12": "Sin gestion registrada",
}

ETIQUETAS_MARCADOR: dict[str, str] = {
    "M04": "Riesgo por comportamiento de pago",
    "M05": "Riesgo por concentracion de cartera",
}


def reglas_de_ambito(ambito: str) -> Iterator[DefinicionRegla]:
    return (r for r in REGLAS if r.ambito == ambito)
