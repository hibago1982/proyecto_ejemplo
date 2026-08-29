"""Motores de alerta de la aplicacion.

Cada motor vive en su propio paquete y se registra en el registro comun. Agregar
el segundo motor es crear el paquete y anadir una linea en `registrar_motores`.
"""

from ..core.motor import registro
from .cartera import MotorCartera


def registrar_motores() -> None:
    """Deja el registro por defecto con todos los motores disponibles."""
    if "cartera" not in registro.codigos():
        registro.registrar(MotorCartera())


__all__ = ["registrar_motores", "registro"]
