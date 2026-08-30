"""Usuarios, roles y autenticacion (§8.4, C-13).

Cierra el hueco que arrastraba el API desde la etapa 3: la empresa llegaba en
una cabecera que el cliente controlaba, de modo que cualquiera podia pedir (y
desde la etapa 6, escribir en) la cartera de otra empresa cambiando un valor.

Ahora la empresa y el rol salen del token, no de la peticion.

Sobre el hash. Se usa PBKDF2-HMAC-SHA256 de la biblioteca estandar, con sal por
usuario y 480.000 iteraciones. No es la opcion mas moderna (Argon2 lo es), pero
no anade dependencias y es solida; si el proyecto adopta `argon2-cffi`, el unico
sitio que cambia es este modulo.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..core.tipos import Rol
from .modelo import Base

#: Coste del derivado. Alto a proposito: es lo que hace cara una fuerza bruta.
#: Las pruebas lo bajan sustituyendo esta variable del modulo; no se lee de una
#: variable de entorno, para que nadie pueda debilitarlo en produccion sin
#: tocar el codigo.
ITERACIONES = 480_000
ALGORITMO = "sha256"


class Usuario(Base):
    """Un usuario del modulo, atado a una empresa y a un rol."""

    __tablename__ = "ar_usuario"
    __table_args__ = (
        UniqueConstraint("usuario", name="uq_usuario_nombre"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario: Mapped[str] = mapped_column(String(64))
    empresa_id: Mapped[str] = mapped_column(String(32), index=True)
    rol: Mapped[int] = mapped_column(Integer)
    nombre: Mapped[str] = mapped_column(String(128), default="")

    clave_hash: Mapped[str] = mapped_column(String(256))
    """Formato: pbkdf2_sha256$<iteraciones>$<sal>$<derivada>. Nunca la clave."""

    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)

    @property
    def rol_enum(self) -> Rol:
        return Rol(self.rol)


@dataclass(frozen=True)
class Identidad:
    """Quien esta haciendo la peticion. Sale del token, no de la peticion."""

    usuario_id: str
    empresa_id: str
    rol: Rol
    nombre: str = ""

    def puede(self, minimo: Rol) -> bool:
        return self.rol.alcanza(minimo)


class ErrorDeAutenticacion(Exception):
    """Credenciales invalidas o usuario inactivo."""


# --------------------------------------------------------------------------
# Claves
# --------------------------------------------------------------------------


def cifrar(clave: str) -> str:
    sal = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac(
        ALGORITMO, clave.encode(), sal.encode(), ITERACIONES
    ).hex()
    # Las iteraciones van dentro del hash: si manana suben, las claves ya
    # guardadas siguen verificandose con el coste con que se crearon.
    return f"pbkdf2_{ALGORITMO}${ITERACIONES}${sal}${derivada}"


def verificar(clave: str, cifrada: str) -> bool:
    """Comprueba la clave en tiempo constante.

    `compare_digest` y no `==`: comparar hashes con el operador normal filtra,
    por el tiempo de respuesta, cuantos caracteres coinciden.
    """
    try:
        _, iteraciones, sal, derivada = cifrada.split("$")
    except ValueError:
        return False
    candidata = hashlib.pbkdf2_hmac(
        ALGORITMO, clave.encode(), sal.encode(), int(iteraciones)
    ).hex()
    return hmac.compare_digest(candidata, derivada)


# --------------------------------------------------------------------------
# Operaciones
# --------------------------------------------------------------------------


def crear(
    sesion: Session,
    usuario: str,
    clave: str,
    empresa_id: str,
    rol: Rol,
    nombre: str = "",
) -> Usuario:
    if sesion.scalar(select(Usuario).where(Usuario.usuario == usuario)):
        raise ValueError(f"El usuario '{usuario}' ya existe.")
    fila = Usuario(
        usuario=usuario, empresa_id=empresa_id, rol=rol.value,
        nombre=nombre, clave_hash=cifrar(clave), activo=True,
    )
    sesion.add(fila)
    sesion.flush()
    return fila


def autenticar(sesion: Session, usuario: str, clave: str) -> Identidad:
    """Devuelve la identidad, o falla sin decir que parte estaba mal.

    El mensaje es el mismo para usuario inexistente, clave incorrecta y usuario
    desactivado: distinguirlos permitiria averiguar que usuarios existen.
    """
    fila = sesion.scalar(select(Usuario).where(Usuario.usuario == usuario))
    if fila is None or not fila.activo or not verificar(clave, fila.clave_hash):
        # Se cifra igualmente cuando el usuario no existe, para que el tiempo de
        # respuesta no revele si el nombre es valido.
        if fila is None:
            cifrar(clave)
        raise ErrorDeAutenticacion("Usuario o clave incorrectos.")

    fila.ultimo_acceso = datetime.utcnow()
    sesion.flush()
    return Identidad(
        usuario_id=fila.usuario, empresa_id=fila.empresa_id,
        rol=fila.rol_enum, nombre=fila.nombre,
    )
