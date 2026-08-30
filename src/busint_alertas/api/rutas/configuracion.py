"""Configuracion (§8.4) y auditoria de cambios (§10.3).

Es la pantalla por la que R01 y R02 se encienden: nacen sin umbral, y la
empresa los fija aqui sin desplegar nada. Cada cambio deja rastro con usuario,
valor anterior y valor nuevo.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...core.parametros import Parametros
from ...core.tipos import FASE_VIGENTE
from ...motores.cartera.reglas import REGLAS
from ...persistencia import configuracion as config_bd
from .. import consultas
from ..dependencias import Empresa, SesionBD
from ..seguridad import Administrador
from ..esquemas import (
    BucketConfigurado,
    CambioParametro,
    Configuracion,
    EntradaAuditoria,
    ReglaConfigurada,
)
from ...persistencia.repositorio import version_de

router = APIRouter(tags=["configuracion"])


@router.get(
    "/configuracion", response_model=Configuracion, summary="Reglas y buckets vigentes"
)
def obtener(sesion: SesionBD, empresa_id: Empresa) -> Configuracion:
    try:
        config = config_bd.cargar(sesion, empresa_id)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None

    buckets = [
        BucketConfigurado(
            codigo=b.codigo, etiqueta=b.etiqueta, desde=b.desde, hasta=b.hasta,
            color=b.color, prioridad_base=b.prioridad_base.value,
            prioridad_etiqueta=b.prioridad_base.etiqueta, accion=b.accion,
            alerta=b.alerta, orden=b.orden, activo=b.activo,
        )
        for b in config.buckets
    ]

    reglas = []
    for regla in REGLAS:
        faltantes = config.parametros.faltantes(regla.parametros_requeridos)
        motivo = regla.inactiva_porque(config.parametros, FASE_VIGENTE)
        propios = {
            n: str(config.parametros.valores[n])
            for n in regla.parametros_requeridos
            if config.parametros.definido(n)
        }
        reglas.append(
            ReglaConfigurada(
                codigo=regla.codigo, etiqueta=regla.etiqueta, ambito=regla.ambito,
                parametros_requeridos=list(regla.parametros_requeridos),
                parametros=propios, faltantes=list(faltantes),
                activa=motivo is None, motivo_inactiva=motivo,
                prioridad=regla.prioridad.value, accion=regla.accion,
            )
        )

    return Configuracion(
        empresa_id=empresa_id, version_parametros=version_de(config),
        buckets=buckets, reglas=reglas,
    )


@router.put(
    "/configuracion/reglas/{codigo}/parametros/{nombre}",
    response_model=Configuracion,
    summary="Fijar el valor de un parametro",
)
def fijar(
    sesion: SesionBD,
    quien: Administrador,
    codigo: str,
    nombre: str,
    cambio: CambioParametro,
) -> Configuracion:
    """§8.4: solo usuarios autorizados modifican reglas. C-13 fija cual rol."""
    regla = next((r for r in REGLAS if r.codigo == codigo), None)
    if regla is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No existe la regla '{codigo}'."
        )
    if nombre not in regla.parametros_requeridos:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"La regla '{codigo}' no usa el parametro '{nombre}'. "
            f"Los suyos son: {', '.join(regla.parametros_requeridos) or 'ninguno'}.",
        )
    _validar(regla, nombre, cambio.valor)

    try:
        config_bd.fijar_parametro(
            sesion, quien.empresa_id, codigo, nombre, cambio.valor, quien.usuario_id
        )
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None
    return obtener(sesion, quien.empresa_id)


def _validar(regla, nombre: str, valor: str) -> None:
    """Un umbral mal escrito debe rechazarse aqui y no reventar en la corrida.

    Sin esta comprobacion, un valor no numerico dejaria la regla guardada pero
    haria fallar el motor en la siguiente ejecucion programada, de madrugada.
    """
    prueba = Parametros({nombre: valor})
    try:
        if nombre.startswith(("dias_", "n_")):
            if prueba.entero(nombre) < 0:
                raise ValueError("no puede ser negativo")
        else:
            if prueba.decimal(nombre) < 0:
                raise ValueError("no puede ser negativo")
    except (ArithmeticError, ValueError) as e:
        # 422 literal: el nombre de la constante cambio entre versiones de
        # Starlette y el numero no.
        raise HTTPException(
            422, f"Valor invalido para '{nombre}': {valor!r} ({e})."
        ) from None


@router.get(
    "/configuracion/auditoria",
    response_model=list[EntradaAuditoria],
    summary="Historial de cambios de configuracion",
)
def historial(
    sesion: SesionBD, empresa_id: Empresa, limite: int = 100
) -> list[EntradaAuditoria]:
    return [
        EntradaAuditoria.model_validate(f)
        for f in consultas.auditoria(sesion, empresa_id, limite)
    ]
