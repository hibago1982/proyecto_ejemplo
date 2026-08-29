"""Configuracion del motor de cartera para una empresa.

Es el equivalente en memoria de `ar_aging_param` + `ar_alert_rule`. En la fase 2
se cargara desde PostgreSQL; en la fase 1 se construye en codigo para poder
probar el motor sin base de datos.

Los rangos de `BUCKETS_BUSINT` se derivaron de las columnas de aging del archivo
de prueba, que son las que el ERP ya calcula:

    Valor por Vencer | <=30 | <=60 | <=90 | <=120 | <=150 | mas de 150

Una diferencia deliberada con el ERP: el archivo mete los saldos de dias=0 en la
columna "vencido menor o igual a 30". Este motor los separa en B01 "vence hoy",
que es lo que exige C-14 para que los indicadores sumen el total. La equivalencia
para reproducir las columnas del ERP en la exportacion de §9 es B01 + B02 = "<=30".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...core.parametros import Parametros
from ...core.tipos import Prioridad
from .buckets import Bucket, ConfiguracionBuckets

#: Buckets de BUSINT, segun las columnas de aging del archivo de prueba (§5.2).
BUCKETS_BUSINT: tuple[Bucket, ...] = (
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
    Bucket("B05", "91 a 120 dias", 91, 120, "#EF4444", Prioridad.CRITICA,
           "Escalar a coordinador", orden=5),
    Bucket("B06", "121 a 150 dias", 121, 150, "#DC2626", Prioridad.CRITICA,
           "Escalar a coordinador", orden=6),
    Bucket("B07", "Mas de 150 dias", 151, None, "#991B1B", Prioridad.CRITICA,
           "Evaluar cobro juridico", orden=7),
)

#: Equivalencia con las columnas de aging del ERP, para la exportacion de §9.
#: El ERP no separa "vence hoy": lo suma dentro de su columna de menor o igual a 30.
COLUMNAS_ERP: dict[str, tuple[str, ...]] = {
    "Valor por Vencer": ("B00",),
    "Valor vencido menor o igual a 30 dias": ("B01", "B02"),
    "Valor vencido menor o igual a 60 dias": ("B03",),
    "Valor vencido menor o igual a 90 dias": ("B04",),
    "Valor vencido menor o igual a 120 dias": ("B05",),
    "Valor vencido menor o igual a 150 dias": ("B06",),
    "Valor vencido a mas de 150": ("B07",),
}

@dataclass
class ConfiguracionCartera:
    """Buckets y parametros de reglas vigentes para una empresa."""

    empresa_id: str
    buckets: ConfiguracionBuckets = field(
        default_factory=lambda: ConfiguracionBuckets(BUCKETS_BUSINT)
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
