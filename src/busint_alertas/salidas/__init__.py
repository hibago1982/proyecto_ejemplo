"""Salidas formales (§9): PDF y Excel, desde el mismo resultado persistido."""

from . import excel, pdf
from .datos import Corte, cargar

__all__ = ["Corte", "cargar", "excel", "pdf"]
