"""Tokens de sesion (§8.4)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("BUSINT_CLAVE_FIRMA", "clave-de-prueba")

from busint_alertas.api.seguridad import ErrorDeToken, emitir, leer  # noqa: E402
from busint_alertas.core.tipos import Rol  # noqa: E402
from busint_alertas.persistencia.usuarios import Identidad  # noqa: E402

ANA = Identidad("ana", "E01", Rol.GESTOR, "Ana Restrepo")


def test_lo_emitido_se_puede_leer():
    token, _ = emitir(ANA)
    leida = leer(token)
    assert (leida.usuario_id, leida.empresa_id, leida.rol) == ("ana", "E01", Rol.GESTOR)


def test_la_empresa_no_se_puede_cambiar_sin_romper_la_firma():
    """Es el punto: hasta la etapa 7 bastaba editar una cabecera."""
    import base64
    import json

    token, _ = emitir(ANA)
    crudo, firma = token.split(".")
    cuerpo = json.loads(base64.urlsafe_b64decode(crudo + "=" * (-len(crudo) % 4)))
    cuerpo["empresa"] = "E99"
    alterado = base64.urlsafe_b64encode(
        json.dumps(cuerpo, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")

    with pytest.raises(ErrorDeToken, match="firma"):
        leer(f"{alterado}.{firma}")


def test_un_token_caducado_se_rechaza():
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    token, _ = emitir(ANA, ahora=ayer)
    with pytest.raises(ErrorDeToken, match="caduco"):
        leer(token)


def test_un_token_sin_punto_no_revienta():
    with pytest.raises(ErrorDeToken, match="mal formado"):
        leer("esto-no-es-un-token")


def test_sin_clave_de_firma_el_api_se_niega_a_emitir(monkeypatch):
    """Una clave por defecto convertiria la firma en decorativa."""
    monkeypatch.delenv("BUSINT_CLAVE_FIRMA", raising=False)
    with pytest.raises(RuntimeError, match="BUSINT_CLAVE_FIRMA"):
        emitir(ANA)
