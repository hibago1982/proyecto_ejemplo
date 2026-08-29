"""Contrato de entrada del motor de cartera: la cuenta por cobrar abierta.

Corresponde a `ar_movimiento` (§6.2), que es una vista de solo lectura sobre las
cuentas abiertas del ERP. El motor nunca escribe aqui.

C-01: los campos se llaman `fecha_emision` y `fecha_vencimiento`, no "inicial" y
"final". La especificacion usaba ambos nombres para cosas distintas en §5.1 y
§10.1, y esa ambiguedad producia dos calculos de dias diferentes.

C-08: `empresa_id` es obligatorio en toda fila. Es la dimension de aislamiento
multiempresa que §8.1 exige y que la estructura de datos de §3 no contemplaba.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.dinero import monto


@dataclass(frozen=True)
class Movimiento:
    """Una factura con saldo abierto, tal como la entrega el ERP."""

    empresa_id: str
    cliente_nit: str
    factura: str
    fecha_emision: date
    fecha_vencimiento: date
    saldo: Decimal
    cliente_nombre: str = ""
    valor_credito: Decimal = Decimal("0.00")
    vendedor: str = ""
    zona: str = ""
    ciudad: str = ""
    contacto: str = ""

    def __post_init__(self) -> None:
        # Se normaliza en el borde de entrada para que ninguna regla tenga que
        # preocuparse por recibir float, str o int desde el conector del ERP.
        object.__setattr__(self, "saldo", monto(self.saldo))
        object.__setattr__(self, "valor_credito", monto(self.valor_credito))
        if self.fecha_vencimiento < self.fecha_emision:
            raise ValueError(
                f"Factura {self.factura}: la fecha de vencimiento "
                f"({self.fecha_vencimiento}) es anterior a la de emision "
                f"({self.fecha_emision})."
            )

    def dias_vencimiento(self, corte: date) -> int:
        """Dias transcurridos desde el vencimiento hasta el corte.

        Positivo si ya vencio, cero si vence hoy, negativo si esta por vencer.
        C-01 fija esta definicion (contra fecha de vencimiento, no de emision):
        se verifico que reproduce exactamente el campo `Dias Vencimiento` de las
        120 filas del archivo de prueba.
        """
        return (corte - self.fecha_vencimiento).days
