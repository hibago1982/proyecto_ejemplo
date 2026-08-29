"""Contrato de datos del API.

De aqui sale el OpenAPI y de el los tipos de TypeScript del frontend, de modo
que un cambio en el backend rompa la compilacion del frontend en vez de fallar
en silencio delante del usuario.

Los montos viajan como cadena y no como numero. Es deliberado: JSON no tiene
decimales exactos, y un `float` de JavaScript no puede representar
1234567.89 sin error. C-09 exige dos decimales conservados en el calculo y en
la exportacion de auditoria; serializar como cadena es lo unico que lo
garantiza de extremo a extremo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

#: Monto con dos decimales, serializado como cadena para no perder precision.
Monto = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
Porcentaje = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]


class Modelo(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Panel de control (§8.1)
# --------------------------------------------------------------------------


class TarjetaKPI(Modelo):
    """Cifra del encabezado con su peso sobre el total.

    El porcentaje viaja calculado desde el servidor: si lo calculara el
    frontend seria una segunda implementacion del indicador, que es justo lo
    que §16 prohibe.
    """

    codigo: str
    etiqueta: str
    valor: Monto
    pct_sobre_total: Porcentaje


class BarraAging(Modelo):
    """Un bucket en el grafico de antiguedad."""

    bucket: str
    etiqueta: str
    color: str
    saldo: Monto
    facturas: int
    pct_sobre_total: Porcentaje


class ClienteEnRanking(Modelo):
    cliente_nit: str
    cliente_nombre: str
    cartera_total: Monto
    vencida: Monto
    pct_vencida: Porcentaje
    pct_90: Porcentaje
    dias_max: int
    n_vencidas: int
    prioridad: int
    prioridad_etiqueta: str
    marcadores: list[str] = Field(default_factory=list)


class Panel(Modelo):
    """Respuesta del panel: todo lo que §8.1 pide, en una sola llamada."""

    empresa_id: str
    corte: date
    generado: datetime | None = None
    version_parametros: str | None = None
    kpis: list[TarjetaKPI]
    aging: list[BarraAging]
    ranking: list[ClienteEnRanking]
    n_clientes: int
    n_facturas: int
    reglas_inactivas: dict[str, str] = Field(default_factory=dict)
    """Reglas que no se evaluaron y por que. §8.4 las muestra como pendientes."""


# --------------------------------------------------------------------------
# Lista de gestion (§8.2)
# --------------------------------------------------------------------------


class FilaGestion(Modelo):
    """Una linea de la bandeja de trabajo."""

    id: int
    cliente_nit: str
    cliente_nombre: str = ""
    """Nombre del cliente. Vive en ar_riesgo_cliente, no en la alerta, asi que
    se resuelve al armar la respuesta: una bandeja de trabajo con solo NIT
    obliga al gestor a buscar a quien llama antes de poder llamarlo."""

    factura: str
    codigo: str
    etiqueta: str
    bucket: str | None
    dias: int | None
    saldo: Monto | None
    saldo_bruto: Monto | None
    credito_aplicado: Monto | None
    prioridad: int
    prioridad_etiqueta: str
    accion: str
    estado: str
    explicacion: str | None
    """Cadena legible de por que se disparo. §7.4: elimina la desconfianza en
    el semaforo, que es la razon habitual por la que estos modulos se abandonan."""

    vendedor: str | None = None
    zona: str | None = None


class ListaGestion(Modelo):
    corte: date
    total: int
    pagina: int
    por_pagina: int
    filas: list[FilaGestion]


# --------------------------------------------------------------------------
# Detalle del cliente (§8.3)
# --------------------------------------------------------------------------


class DetalleCliente(Modelo):
    cliente_nit: str
    cliente_nombre: str
    corte: date
    cartera_total: Monto
    por_vencer: Monto
    vence_hoy: Monto
    vencida: Monto
    pct_vencida: Porcentaje
    mayor_90: Monto
    pct_90: Porcentaje
    mayor_150: Monto
    dias_max: int
    n_facturas: int
    n_vencidas: int
    prioridad: int
    prioridad_etiqueta: str
    marcadores: list[str]
    alertas: list[FilaGestion]
    gestiones: list[Gestion] = Field(default_factory=list)
    """Historial de cobranza (§8.3), de lo mas reciente a lo mas antiguo."""


# --------------------------------------------------------------------------
# Gestion de cobranza (§11)
# --------------------------------------------------------------------------


class NuevaGestion(BaseModel):
    """Lo que registra el gestor tras contactar al cliente.

    El compromiso de pago es opcional, pero si va, van sus dos partes: media
    promesa no se puede seguir.
    """

    factura: str = Field(default="", description="Vacio para una alerta de cliente.")
    tipo: str = Field(description="llamada, correo, mensaje, visita, acuerdo, disputa u otra")
    usuario_id: str = Field(min_length=1, max_length=64)
    resultado: str | None = Field(default=None, max_length=64)
    observacion: str | None = None
    compromiso_fecha: date | None = None
    compromiso_valor: Decimal | None = None


class Gestion(Modelo):
    id: int
    cliente_nit: str
    factura: str
    fecha: datetime
    corte: date | None
    usuario_id: str
    tipo: str
    resultado: str | None
    compromiso_fecha: date | None
    compromiso_valor: Monto | None
    observacion: str | None


# --------------------------------------------------------------------------
# Configuracion (§8.4)
# --------------------------------------------------------------------------


class BucketConfigurado(Modelo):
    codigo: str
    etiqueta: str
    desde: int | None
    hasta: int | None
    color: str
    prioridad_base: int
    prioridad_etiqueta: str
    accion: str
    alerta: str | None
    orden: int
    activo: bool


class ReglaConfigurada(Modelo):
    codigo: str
    etiqueta: str
    ambito: str
    parametros_requeridos: list[str]
    parametros: dict[str, str]
    faltantes: list[str]
    """Parametros sin valor. Mientras haya alguno, la regla no se evalua (C-05)."""

    activa: bool
    motivo_inactiva: str | None
    prioridad: int
    accion: str


class Configuracion(Modelo):
    empresa_id: str
    version_parametros: str
    buckets: list[BucketConfigurado]
    reglas: list[ReglaConfigurada]


class CambioParametro(BaseModel):
    """Peticion para fijar un umbral.

    Es el camino por el que R01 y R02 se activan: sin despliegue, con rastro.
    """

    valor: str = Field(description="Valor nuevo. Se guarda como texto y la regla lo interpreta.")
    usuario_id: str = Field(min_length=1, max_length=64)


class EntradaAuditoria(Modelo):
    fecha_hora: datetime
    usuario_id: str
    entidad: str
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None


# --------------------------------------------------------------------------
# Ejecucion del motor (§10.2)
# --------------------------------------------------------------------------


class PeticionEjecucion(BaseModel):
    corte: date | None = Field(
        default=None,
        description="Corte a procesar. Si se omite, se usa la fecha de hoy en "
        "America/Bogota, que es la zona de referencia del motor (C-11).",
    )


class ResultadoEjecucion(Modelo):
    empresa_id: str
    corte: date
    filas_leidas: int
    alertas_insertadas: int
    alertas_actualizadas: int
    alertas_cerradas: int
    clientes: int
    version_parametros: str
    reglas_inactivas: dict[str, str]


class Ejecucion(Modelo):
    corte: date
    inicio: datetime
    fin: datetime | None
    filas_procesadas: int
    alertas_generadas: int
    alertas_cerradas: int
    estado: str
    mensaje: str | None


class Corte(Modelo):
    """Un corte disponible para consultar o reproducir."""

    corte: date
    generado: datetime
    version_parametros: str
    cartera_total: Monto
    n_clientes: int
