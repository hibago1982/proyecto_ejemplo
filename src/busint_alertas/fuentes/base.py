"""Origenes de datos del motor.

§4.2 dice que el origen son las cuentas por cobrar abiertas del ERP, "expuestas
via API o lectura directa de la base", y §4.3 anade que al migrar del escenario
A al B "lo unico que cambia es el conector de datos". Esta capa es ese conector.

Todas las fuentes producen `Movimiento`, de modo que el motor no sabe ni le
importa si los datos llegaron de un Excel, de un API REST o de una consulta SQL.
Esa indiferencia es lo que permite probar el motor contra un archivo y correrlo
en produccion contra el ERP sin tocar una linea de logica.

El mapeo de campos vive aqui y no en el motor a proposito: es el contrato de
datos de la etapa 0, y es lo que hay que ajustar cuando el ERP cambia un nombre
de columna. Ajustarlo es editar un `MapeoCampos`, no reescribir codigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Iterator, Mapping, Protocol, runtime_checkable

from ..motores.cartera.datos import Movimiento


class ErrorDeOrigen(RuntimeError):
    """Falla al leer o interpretar los datos del origen."""


@dataclass(frozen=True)
class MapeoCampos:
    """Traduce los nombres del origen a los del motor.

    Cada atributo guarda el nombre de la columna o clave en el origen. Los
    campos opcionales pueden quedar en None si el origen no los expone.
    """

    cliente_nit: str
    factura: str
    fecha_emision: str
    fecha_vencimiento: str
    saldo: str

    cliente_nombre: str | None = None
    valor_credito: str | None = None
    vendedor: str | None = None
    zona: str | None = None
    ciudad: str | None = None
    contacto: str | None = None

    empresa_id: str | None = None
    """Columna que trae la empresa. Si es None se usa `empresa_id_fijo`.

    C-08: el archivo de prueba de Busint no tiene columna de empresa, asi que
    hoy se inyecta como constante. Cuando el ERP la exponga, basta con nombrarla
    aqui y borrar la constante.
    """

    empresa_id_fijo: str | None = None

    fecha_corte: str | None = None
    """Columna con la fecha de corte del extracto, si el origen la trae.

    Sirve para verificar que el archivo que se esta leyendo corresponde al corte
    que se pidio, y no a uno viejo.
    """

    def empresa_de(self, registro: Mapping[str, Any]) -> str:
        if self.empresa_id is not None:
            valor = registro.get(self.empresa_id)
            if valor not in (None, ""):
                return str(valor).strip()
        if self.empresa_id_fijo is not None:
            return self.empresa_id_fijo
        raise ErrorDeOrigen(
            "El registro no trae empresa y el mapeo no define 'empresa_id_fijo'. "
            "El aislamiento por empresa es obligatorio (C-08)."
        )


@runtime_checkable
class FuenteDatos(Protocol):
    """Contrato que cumple todo origen de cuentas por cobrar abiertas."""

    def leer(self, empresa_id: str, corte: date) -> Iterator[Movimiento]:
        """Entrega las cuentas abiertas de una empresa a una fecha de corte.

        `corte` no siempre filtra: un archivo plano ya viene cortado y solo se
        verifica, mientras que un API puede recibirlo como parametro. Lo que si
        se garantiza es que lo devuelto corresponde a esa empresa.
        """
        ...


# --------------------------------------------------------------------------
# Normalizacion
# --------------------------------------------------------------------------


def _a_fecha(valor: Any, campo: str, factura: str) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    raise ErrorDeOrigen(
        f"Factura {factura}: no se pudo interpretar '{campo}' con valor {valor!r} como fecha."
    )


def _a_decimal(valor: Any, campo: str, factura: str) -> Decimal:
    if valor in (None, ""):
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    # Formato colombiano: 1.234.567,89 -> 1234567.89
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ErrorDeOrigen(
            f"Factura {factura}: no se pudo interpretar '{campo}' con valor {valor!r} como monto."
        ) from None


def _texto(registro: Mapping[str, Any], clave: str | None) -> str:
    if clave is None:
        return ""
    valor = registro.get(clave)
    return "" if valor is None else str(valor).strip()


def construir_movimiento(
    registro: Mapping[str, Any], mapeo: MapeoCampos
) -> Movimiento:
    """Convierte un registro crudo del origen en un `Movimiento` validado.

    Toda la normalizacion (fechas en varios formatos, montos con separadores
    colombianos, numeros que llegan como texto) ocurre aqui y solo aqui, para
    que ninguna fuente tenga que repetirla y el motor nunca vea datos crudos.
    """
    factura = _texto(registro, mapeo.factura) or "(sin numero)"
    faltantes = [
        c
        for c in (mapeo.cliente_nit, mapeo.fecha_emision, mapeo.fecha_vencimiento, mapeo.saldo)
        if c not in registro
    ]
    if faltantes:
        raise ErrorDeOrigen(
            f"Factura {factura}: el origen no trae las columnas {faltantes}. "
            f"Revisa el MapeoCampos contra el modelo real."
        )

    return Movimiento(
        empresa_id=mapeo.empresa_de(registro),
        cliente_nit=_texto(registro, mapeo.cliente_nit),
        factura=factura,
        fecha_emision=_a_fecha(registro[mapeo.fecha_emision], mapeo.fecha_emision, factura),
        fecha_vencimiento=_a_fecha(
            registro[mapeo.fecha_vencimiento], mapeo.fecha_vencimiento, factura
        ),
        saldo=_a_decimal(registro[mapeo.saldo], mapeo.saldo, factura),
        cliente_nombre=_texto(registro, mapeo.cliente_nombre),
        valor_credito=_a_decimal(
            registro.get(mapeo.valor_credito) if mapeo.valor_credito else 0,
            mapeo.valor_credito or "valor_credito",
            factura,
        ),
        vendedor=_texto(registro, mapeo.vendedor),
        zona=_texto(registro, mapeo.zona),
        ciudad=_texto(registro, mapeo.ciudad),
        contacto=_texto(registro, mapeo.contacto),
    )


def normalizar(
    registros: Iterable[Mapping[str, Any]],
    mapeo: MapeoCampos,
    empresa_id: str,
) -> Iterator[Movimiento]:
    """Convierte y filtra por empresa. Lo comparten todas las fuentes."""
    for registro in registros:
        movimiento = construir_movimiento(registro, mapeo)
        if movimiento.empresa_id == empresa_id:
            yield movimiento
