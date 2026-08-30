"""Conexion y creacion del esquema.

El motor de produccion es PostgreSQL 16. SQLite se admite para pruebas: los
modelos son portables y lo que no lo es (particionado, indices JSONB, seguridad
a nivel de fila) esta en las migraciones y no en el modelo.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import usuarios  # noqa: F401  (registra ar_usuario antes de create_all)
from .modelo import Base


def crear_engine(url: str, **opciones) -> Engine:
    """Crea el engine. La URL nunca se arma aqui: llega ya resuelta.

    Asi la credencial vive en la configuracion del despliegue y no en el codigo.
    """
    return create_engine(url, **opciones)


def crear_esquema(engine: Engine) -> None:
    """Crea las tablas. En produccion esto lo hace Alembic, no esta funcion.

    Existe para pruebas y para levantar un entorno de desarrollo de cero.
    """
    Base.metadata.create_all(engine)


def fabrica_de_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
