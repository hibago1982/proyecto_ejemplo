"""Inicio de sesion (§8.4, C-13)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...persistencia.usuarios import ErrorDeAutenticacion, autenticar
from ..dependencias import SesionBD
from ..esquemas import Credenciales, Sesion
from ..seguridad import Quien, emitir

router = APIRouter(tags=["sesion"])


@router.post("/sesion", response_model=Sesion, summary="Iniciar sesion")
def iniciar(sesion: SesionBD, credenciales: Credenciales) -> Sesion:
    try:
        identidad = autenticar(sesion, credenciales.usuario, credenciales.clave)
    except ErrorDeAutenticacion as e:
        # 401 con el mismo texto para todos los casos: distinguir "no existe" de
        # "clave incorrecta" permitiria averiguar que usuarios hay.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    token, expira = emitir(identidad)
    return Sesion(
        token=token, expira=expira, usuario_id=identidad.usuario_id,
        empresa_id=identidad.empresa_id, rol=identidad.rol.value,
        rol_etiqueta=identidad.rol.etiqueta, nombre=identidad.nombre,
    )


@router.get("/sesion", response_model=Sesion, summary="Quien soy")
def quien_soy(quien: Quien) -> Sesion:
    """Permite al frontend recuperar la identidad sin volver a pedir la clave."""
    token, expira = emitir(quien)
    return Sesion(
        token=token, expira=expira, usuario_id=quien.usuario_id,
        empresa_id=quien.empresa_id, rol=quien.rol.value,
        rol_etiqueta=quien.rol.etiqueta, nombre=quien.nombre,
    )
