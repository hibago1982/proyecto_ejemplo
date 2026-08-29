"""La alerta y su explicacion.

El principio de explicabilidad de §7.4 no es una funcion de la interfaz: si la
explicacion se arma en el frontend, se convierte en una segunda implementacion
de la regla y contradice §16 (una sola fuente de calculo). Por eso cada alerta
nace con la cadena completa de por que se disparo, y pantalla, PDF y Excel se
limitan a mostrarla.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .tipos import EstadoAlerta, Prioridad


@dataclass(frozen=True)
class Explicacion:
    """Por que esta alerta existe, en terminos que un gerente pueda auditar."""

    regla: str
    """Codigo de la regla que la disparo, p. ej. 'R03'."""

    motivo: str
    """Frase legible: 'el cliente tiene 4 facturas vencidas'."""

    parametro: str | None = None
    """Nombre del parametro vigente que se comparo, p. ej. 'n_facturas_vencidas'."""

    valor_parametro: Any = None
    """Valor que tenia ese parametro en el momento del calculo."""

    valor_observado: Any = None
    """Valor real que se comparo contra el parametro."""

    def __str__(self) -> str:
        if self.parametro is None:
            return f"{self.regla}: {self.motivo}"
        return (
            f"{self.regla}: {self.motivo} "
            f"({self.valor_observado} contra {self.parametro}={self.valor_parametro})"
        )


@dataclass(frozen=True)
class Alerta:
    """Una alerta emitida por un motor sobre una entidad concreta.

    `entidad` identifica sobre que se emitio (en cartera, el numero de factura)
    y `sujeto` a quien afecta (el NIT del cliente). Esa separacion permite que
    un motor de inventario use la misma estructura con otra semantica.
    """

    codigo: str
    """Identificador del catalogo, p. ej. 'A10'."""

    etiqueta: str
    prioridad: Prioridad
    accion: str
    sujeto: str
    entidad: str | None = None
    explicacion: Explicacion | None = None
    estado: EstadoAlerta = EstadoAlerta.ACTIVA
    datos: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Marcador:
    """Senal de riesgo a nivel de sujeto, que no es una alerta de entidad.

    C-04: R04 y R05 producen el efecto de "marcar riesgo" pero no tienen
    identificador en el catalogo de alertas. Se modelan como marcadores del
    cliente, no como alertas de factura, y se persisten en `ar_riesgo_cliente`.
    """

    codigo: str
    etiqueta: str
    sujeto: str
    explicacion: Explicacion | None = None
