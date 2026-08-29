"""Origen por API REST contra el ERP.

Es el modo previsto para produccion en el escenario A de §4.3: el motor corre
como servicio aparte y le pide al ERP las cuentas abiertas, sin tocar su base.

El transporte esta inyectado a proposito. Permite probar la fuente sin red y,
mas adelante, cambiar urllib por httpx (reintentos, pool de conexiones) sin
tocar la logica de paginacion ni el mapeo.

Advertencia: la forma de la respuesta y el esquema de paginacion son
parametrizables porque el API real de Busint todavia no esta definida. Los
valores por defecto siguen la convencion mas comun, pero hay que confirmarlos
contra el contrato real antes de usar en produccion.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterator, Mapping, Protocol, runtime_checkable

from ..motores.cartera.datos import Movimiento
from .base import ErrorDeOrigen, MapeoCampos, normalizar


@runtime_checkable
class Transporte(Protocol):
    """Lo minimo que necesita la fuente para hablar con el ERP."""

    def obtener(self, url: str, cabeceras: Mapping[str, str]) -> Any: ...


@dataclass
class TransporteHTTP:
    """Transporte sobre la biblioteca estandar. Sin dependencias externas."""

    tiempo_limite: float = 30.0

    def obtener(self, url: str, cabeceras: Mapping[str, str]) -> Any:
        peticion = urllib.request.Request(url, headers=dict(cabeceras))
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_limite) as resp:
                cuerpo = resp.read()
        except urllib.error.HTTPError as e:
            raise ErrorDeOrigen(
                f"El ERP respondio {e.code} al pedir {_sin_credenciales(url)}: {e.reason}"
            ) from None
        except urllib.error.URLError as e:
            raise ErrorDeOrigen(
                f"No se pudo contactar al ERP en {_sin_credenciales(url)}: {e.reason}"
            ) from None
        try:
            return json.loads(cuerpo)
        except json.JSONDecodeError:
            raise ErrorDeOrigen(
                f"El ERP no devolvio JSON valido en {_sin_credenciales(url)}."
            ) from None


@dataclass
class FuenteAPI:
    """Lee las cuentas abiertas del ERP por HTTP.

    El token se guarda aqui y no se escribe en logs ni en mensajes de error:
    `_sin_credenciales` limpia las URL antes de reportarlas.
    """

    url_base: str
    mapeo: MapeoCampos
    token: str | None = None
    transporte: Transporte = field(default_factory=TransporteHTTP)
    ruta: str = "/cuentas-por-cobrar/abiertas"
    campo_datos: str = "datos"
    """Clave del JSON que contiene la lista de registros."""

    campo_siguiente: str = "siguiente"
    """Clave con la URL de la pagina siguiente. None o ausente termina el recorrido."""

    tamano_pagina: int = 500
    max_paginas: int = 10_000
    """Tope de seguridad: un API que devuelva siempre la misma pagina siguiente
    colgaria el proceso indefinidamente."""

    def leer(self, empresa_id: str, corte: date) -> Iterator[Movimiento]:
        return normalizar(self._registros(empresa_id, corte), self.mapeo, empresa_id)

    def _registros(self, empresa_id: str, corte: date) -> Iterator[Mapping[str, Any]]:
        parametros = urllib.parse.urlencode(
            {"empresa": empresa_id, "corte": corte.isoformat(), "limite": self.tamano_pagina}
        )
        url = f"{self.url_base.rstrip('/')}{self.ruta}?{parametros}"
        vistas: set[str] = set()

        for _ in range(self.max_paginas):
            if url in vistas:
                raise ErrorDeOrigen(
                    f"El API devolvio una pagina repetida ({_sin_credenciales(url)}); "
                    "se corta para no entrar en bucle."
                )
            vistas.add(url)

            respuesta = self.transporte.obtener(url, self._cabeceras())
            yield from self._extraer(respuesta, url)

            url = self._siguiente(respuesta)
            if url is None:
                return

        raise ErrorDeOrigen(
            f"Se superaron las {self.max_paginas} paginas leyendo del ERP."
        )

    def _cabeceras(self) -> dict[str, str]:
        cabeceras = {"Accept": "application/json"}
        if self.token:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        return cabeceras

    def _extraer(self, respuesta: Any, url: str) -> list[Mapping[str, Any]]:
        if isinstance(respuesta, list):
            return respuesta
        if isinstance(respuesta, Mapping):
            datos = respuesta.get(self.campo_datos)
            if isinstance(datos, list):
                return datos
            raise ErrorDeOrigen(
                f"La respuesta de {_sin_credenciales(url)} no trae la lista '{self.campo_datos}'. "
                f"Claves recibidas: {sorted(respuesta)}."
            )
        raise ErrorDeOrigen(
            f"Respuesta inesperada de {_sin_credenciales(url)}: se esperaba objeto o lista."
        )

    def _siguiente(self, respuesta: Any) -> str | None:
        if not isinstance(respuesta, Mapping):
            return None
        siguiente = respuesta.get(self.campo_siguiente)
        return str(siguiente) if siguiente else None


def _sin_credenciales(url: str) -> str:
    """Quita usuario, contrasena y tokens de una URL antes de reportarla.

    Un mensaje de error termina en los logs y a veces en un ticket; no debe
    llevar credenciales dentro.
    """
    partes = urllib.parse.urlsplit(url)
    red = partes.hostname or ""
    if partes.port:
        red = f"{red}:{partes.port}"
    consulta = [
        (k, "***" if k.lower() in {"token", "apikey", "api_key", "access_token", "clave"} else v)
        for k, v in urllib.parse.parse_qsl(partes.query)
    ]
    return urllib.parse.urlunsplit(
        (partes.scheme, red, partes.path, urllib.parse.urlencode(consulta), "")
    )
