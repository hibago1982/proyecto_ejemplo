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
    """Saldo sobre el que operan las reglas.

    Antes de aplicar creditos es el saldo bruto del ERP; despues de
    `aplicar_creditos` es el saldo neto. Las reglas usan siempre este campo, de
    modo que ninguna tiene que saber si hubo notas credito o no.
    """

    cliente_nombre: str = ""
    valor_credito: Decimal = Decimal("0.00")
    """Nota credito o abono sin aplicar que trae el ERP en esta fila.

    C-10: no viene neteado contra el saldo. Es un credito del cliente, no de
    esta factura en particular, y se aplica a la mas antigua.
    """

    saldo_bruto: Decimal | None = None
    """Saldo original, antes de aplicar creditos. None si aun no se aplicaron."""

    credito_aplicado: Decimal = Decimal("0.00")
    """Cuanto credito absorbio esta factura."""

    vendedor: str = ""
    zona: str = ""
    ciudad: str = ""
    contacto: str = ""

    def __post_init__(self) -> None:
        # Se normaliza en el borde de entrada para que ninguna regla tenga que
        # preocuparse por recibir float, str o int desde el conector del ERP.
        object.__setattr__(self, "saldo", monto(self.saldo))
        object.__setattr__(self, "valor_credito", monto(self.valor_credito))
        object.__setattr__(self, "credito_aplicado", monto(self.credito_aplicado))
        if self.saldo_bruto is not None:
            object.__setattr__(self, "saldo_bruto", monto(self.saldo_bruto))
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

    @property
    def orden_antiguedad(self) -> tuple:
        """Clave para ordenar de mas antigua a mas reciente.

        Se ordena por vencimiento y no por emision porque en cartera "la mas
        antigua" es la que lleva mas dias vencida. El numero de factura entra
        como desempate para que el resultado no dependa del orden de llegada.
        """
        return (self.fecha_vencimiento, self.fecha_emision, self.factura)
