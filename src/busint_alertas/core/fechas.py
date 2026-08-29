"""Manejo de fechas y zona horaria del motor.

C-11: "fecha actual" y "vence hoy" son ambiguos sin zona horaria. El motor fija
America/Bogota como referencia, independientemente de donde se despliegue el
servidor, para que un job nocturno no clasifique mal el bucket "vence hoy".
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_MOTOR = ZoneInfo("America/Bogota")


def hoy() -> date:
    """Fecha de hoy en la zona horaria del motor, no la del servidor."""
    return datetime.now(ZONA_MOTOR).date()


def ahora() -> datetime:
    """Instante actual, con zona horaria explicita."""
    return datetime.now(ZONA_MOTOR)


def dias_entre(desde: date, hasta: date) -> int:
    """Dias calendario entre dos fechas, con signo.

    Positivo cuando `hasta` es posterior. Se usa para los dias de vencimiento:
    `dias_entre(fecha_vencimiento, corte)` es positivo si ya vencio.
    """
    return (hasta - desde).days
