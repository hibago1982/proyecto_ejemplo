"""Autenticacion del API (§8.4, C-13).

Reemplaza la cabecera `X-Empresa-Id`, que era un marcador de posicion desde la
etapa 3: cualquiera podia leer y, desde la etapa 6, escribir en la cartera de
otra empresa cambiando un valor de la peticion.

Ahora la empresa y el rol salen del token firmado, y el cliente no puede
alterarlos sin invalidar la firma.

Sobre el formato del token. Es un valor firmado con HMAC-SHA256 sobre una clave
del despliegue, no un JWT: no hace falta interoperar con terceros y evita
arrastrar una libreria mas para algo que la biblioteca estandar resuelve. Si
manana el ERP necesita federar sesiones, este modulo es el unico que cambia.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..core.tipos import Rol
from ..persistencia.usuarios import Identidad

VIGENCIA = timedelta(hours=12)


class ErrorDeToken(Exception):
    """El token falta, esta mal formado, caduco o fue manipulado."""


def _clave() -> bytes:
    """Clave de firma del despliegue.

    Falla en el arranque si no esta puesta. Es deliberado: un valor por defecto
    convertiria la firma en decorativa, porque cualquiera que conozca el codigo
    podria emitir tokens validos.
    """
    valor = os.environ.get("BUSINT_CLAVE_FIRMA")
    if not valor:
        raise RuntimeError(
            "Falta la variable BUSINT_CLAVE_FIRMA. Sin ella los tokens no se "
            "pueden firmar, y una clave por defecto no seria una firma."
        )
    return valor.encode()


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def emitir(identidad: Identidad, ahora: datetime | None = None) -> tuple[str, datetime]:
    """Firma un token para esa identidad. Devuelve el token y su caducidad."""
    inicio = ahora or datetime.now(timezone.utc)
    expira = inicio + VIGENCIA
    cuerpo = {
        "usuario": identidad.usuario_id,
        "empresa": identidad.empresa_id,
        "rol": identidad.rol.value,
        "nombre": identidad.nombre,
        "exp": int(expira.timestamp()),
    }
    crudo = _b64(json.dumps(cuerpo, sort_keys=True, separators=(",", ":")).encode())
    firma = _b64(hmac.new(_clave(), crudo.encode(), sha256).digest())
    return f"{crudo}.{firma}", expira


def leer(token: str, ahora: datetime | None = None) -> Identidad:
    """Valida la firma y la vigencia, y devuelve la identidad."""
    try:
        crudo, firma = token.split(".")
    except ValueError:
        raise ErrorDeToken("Token mal formado.") from None

    esperada = _b64(hmac.new(_clave(), crudo.encode(), sha256).digest())
    if not hmac.compare_digest(firma, esperada):
        raise ErrorDeToken("La firma del token no es valida.")

    try:
        cuerpo = json.loads(_de_b64(crudo))
    except (ValueError, UnicodeDecodeError):
        raise ErrorDeToken("El contenido del token no se pudo leer.") from None

    momento = ahora or datetime.now(timezone.utc)
    if momento.timestamp() > cuerpo.get("exp", 0):
        raise ErrorDeToken("El token caduco. Vuelve a iniciar sesion.")

    return Identidad(
        usuario_id=cuerpo["usuario"],
        empresa_id=cuerpo["empresa"],
        rol=Rol(cuerpo["rol"]),
        nombre=cuerpo.get("nombre", ""),
    )


# --------------------------------------------------------------------------
# Dependencias de FastAPI
# --------------------------------------------------------------------------


def identidad_actual(peticion: Request) -> Identidad:
    cabecera = peticion.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Falta el token. Autenticate en POST /api/v1/sesion.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return leer(cabecera.removeprefix("Bearer ").strip())
    except ErrorDeToken as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


Quien = Annotated[Identidad, Depends(identidad_actual)]


def exige(minimo: Rol):
    """Dependencia que exige un rol minimo.

    Los permisos son acumulativos, asi que basta declarar el suelo de cada
    endpoint y no enumerar quien puede.
    """

    def comprobar(quien: Quien) -> Identidad:
        if not quien.puede(minimo):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Tu rol ({quien.rol.etiqueta}) no permite esta operacion. "
                f"Requiere al menos: {minimo.etiqueta}.",
            )
        return quien

    return comprobar


Consulta = Annotated[Identidad, Depends(exige(Rol.CONSULTA))]
Gestor = Annotated[Identidad, Depends(exige(Rol.GESTOR))]
Coordinador = Annotated[Identidad, Depends(exige(Rol.COORDINADOR))]
Administrador = Annotated[Identidad, Depends(exige(Rol.ADMINISTRADOR))]
