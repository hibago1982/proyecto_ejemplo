"""Configuracion del motor de cartera para una empresa.

Es el equivalente en memoria de `ar_aging_param` + `ar_alert_rule`. En la fase 2
se cargara desde PostgreSQL; en la fase 1 se construye en codigo para poder
probar el motor sin base de datos.

Advertencia sobre los rangos por defecto: la plantilla de abajo es una propuesta
coherente con los indicadores de §6 (que hablan de cortes en 90 y 150 dias),
pero los rangos reales estan en §5.2 de la Especificacion Funcional v1.0, que
no llego con este documento. Deben confirmarse antes de usar en produccion.
Cambiarlos es editar esta plantilla, no el motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...core.parametros import Parametros
from ...core.tipos import Prioridad
from .buckets import Bucket, ConfiguracionBuckets

#: Plantilla de buckets. PENDIENTE de confirmar contra §5.2.
BUCKETS_PLANTILLA: tuple[Bucket, ...] = (
    Bucket("B00", "Por vencer", None, -1, "#64748B", Prioridad.INFORMATIVA,
           "Sin accion", orden=0),
    Bucket("B01", "Vence hoy", 0, 0, "#0EA5E9", Prioridad.MEDIA,
           "Confirmar pago", orden=1),
    Bucket("B02", "1 a 30 dias", 1, 30, "#FACC15", Prioridad.MEDIA,
           "Contactar al cliente", orden=2),
    Bucket("B03", "31 a 60 dias", 31, 60, "#FB923C", Prioridad.ALTA,
           "Contactar al cliente", orden=3),
    Bucket("B04", "61 a 90 dias", 61, 90, "#F97316", Prioridad.ALTA,
           "Escalar a coordinador", orden=4),
    Bucket("B05", "91 a 150 dias", 91, 150, "#EF4444", Prioridad.CRITICA,
           "Escalar a coordinador", orden=5),
    Bucket("B06", "Mas de 150 dias", 151, None, "#991B1B", Prioridad.CRITICA,
           "Evaluar cobro juridico", orden=6),
)


@dataclass
class ConfiguracionCartera:
    """Buckets y parametros de reglas vigentes para una empresa."""

    empresa_id: str
    buckets: ConfiguracionBuckets = field(
        default_factory=lambda: ConfiguracionBuckets(BUCKETS_PLANTILLA)
    )
    parametros: Parametros = field(default_factory=Parametros)
    """Parametros de todas las reglas, en un solo mapa.

    Los nombres son unicos entre reglas (C-06 elimino el 'X' compartido), asi
    que un mapa plano basta y evita tener que saber a que regla pertenece cada
    umbral antes de poder leerlo.
    """

    @classmethod
    def plantilla(cls, empresa_id: str, **parametros) -> "ConfiguracionCartera":
        """Configuracion de arranque, con los parametros que se quieran fijar.

        Todo parametro no pasado queda sin definir, y su regla inactiva (C-05).
        """
        return cls(empresa_id=empresa_id, parametros=Parametros(dict(parametros)))
