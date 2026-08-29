"""Las migraciones tienen que llevar a un esquema igual al del modelo.

Esta prueba nace de un fallo real: la revision 0001 creaba las tablas con
`Base.metadata.create_all`, de modo que describia el modelo de hoy en vez del
esquema de su propia revision. En una base nueva la 0002 fallaba al anadir una
columna que la 0001 ya habia creado, y el fallo solo aparecia al escribir la
segunda migracion, no al escribir la primera.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("alembic")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402

from busint_alertas.persistencia.modelo import Base  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent


def configuracion(url: str) -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migraciones"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'migrada.db'}"


def test_las_migraciones_llegan_hasta_el_final(url):
    command.upgrade(configuracion(url), "head")
    tablas = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tablas


def test_el_esquema_migrado_coincide_con_el_modelo(url):
    """Si una columna se anade al modelo sin migracion, esto lo detecta."""
    command.upgrade(configuracion(url), "head")
    inspector = inspect(create_engine(url))

    for nombre, tabla in Base.metadata.tables.items():
        migradas = {c["name"] for c in inspector.get_columns(nombre)}
        del_modelo = {c.name for c in tabla.columns}
        assert del_modelo == migradas, (
            f"{nombre}: el modelo y la migracion no coinciden. "
            f"Solo en el modelo: {del_modelo - migradas}. "
            f"Solo en la migracion: {migradas - del_modelo}."
        )


def test_cada_revision_se_aplica_por_separado(url):
    """Aplicar 0001 y luego 0002 debe funcionar igual que ir directo a head.

    Es exactamente el caso que fallaba: 0001 creaba de mas y 0002 chocaba.
    """
    cfg = configuracion(url)
    command.upgrade(cfg, "0001")
    columnas = {c["name"] for c in inspect(create_engine(url)).get_columns("ar_alerta")}
    assert "primer_corte" not in columnas, (
        "La revision 0001 no debe crear columnas que introduce la 0002."
    )
    command.upgrade(cfg, "head")
    columnas = {c["name"] for c in inspect(create_engine(url)).get_columns("ar_alerta")}
    assert "primer_corte" in columnas


def test_el_downgrade_deshace_todo(url):
    cfg = configuracion(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    tablas = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) & tablas == set()
