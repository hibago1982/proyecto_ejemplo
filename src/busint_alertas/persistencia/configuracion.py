"""Carga y guardado de la configuracion desde la base.

§8.4 pide parametrizar sin tocar codigo, y §16 lo refuerza: los rangos de dias
no se escriben en el codigo. Este modulo es el puente entre las tablas
`ar_aging_param` y `ar_alert_rule` y la `ConfiguracionCartera` que consume el
motor, de modo que cambiar un umbral sea un UPDATE y no un despliegue.

Todo cambio de parametro pasa por `ar_auditoria_config` con valor anterior y
nuevo, que es lo que §10.3 exige de forma literal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.parametros import Parametros
from ..core.tipos import Prioridad
from ..motores.cartera.buckets import Bucket, ConfiguracionBuckets
from ..motores.cartera.configuracion import BUCKETS_BUSINT, ConfiguracionCartera
from ..motores.cartera.reglas import REGLAS
from . import modelo


def sembrar(sesion: Session, empresa_id: str, **parametros: Any) -> None:
    """Deja una empresa con los buckets de §5.2 y sus reglas declaradas.

    Los parametros que no se pasen quedan sin valor, y su regla inactiva. Es
    deliberado: §16 prohibe fijar umbrales monetarios desde la base de
    demostracion, asi que el arranque no inventa ninguno.
    """
    ya_tiene = sesion.scalar(
        select(modelo.AgingParam.id).where(
            modelo.AgingParam.empresa_id == empresa_id
        )
    )
    if ya_tiene is None:
        for b in BUCKETS_BUSINT:
            sesion.add(
                modelo.AgingParam(
                    empresa_id=empresa_id, codigo=b.codigo, etiqueta=b.etiqueta,
                    desde=b.desde, hasta=b.hasta, color=b.color,
                    prioridad_base=b.prioridad_base.value, accion=b.accion,
                    alerta=b.alerta, orden=b.orden, activo=b.activo,
                )
            )

    existentes = {
        r.codigo
        for r in sesion.scalars(
            select(modelo.AlertRule).where(
                modelo.AlertRule.empresa_id == empresa_id
            )
        )
    }
    for regla in REGLAS:
        if regla.codigo in existentes:
            continue
        propios = {
            n: parametros[n] for n in regla.parametros_requeridos if n in parametros
        }
        sesion.add(
            modelo.AlertRule(
                empresa_id=empresa_id, codigo=regla.codigo, tipo=regla.ambito,
                parametros={k: str(v) for k, v in propios.items()},
                prioridad=regla.prioridad.value, accion=regla.accion, activo=True,
            )
        )
    sesion.flush()


def cargar(sesion: Session, empresa_id: str) -> ConfiguracionCartera:
    """Reconstruye la configuracion vigente de una empresa."""
    filas = list(
        sesion.scalars(
            select(modelo.AgingParam)
            .where(modelo.AgingParam.empresa_id == empresa_id)
            .order_by(modelo.AgingParam.orden)
        )
    )
    if not filas:
        raise LookupError(
            f"La empresa '{empresa_id}' no tiene buckets configurados. "
            "Ejecuta `sembrar` antes de correr el motor."
        )

    buckets = ConfiguracionBuckets([
        Bucket(
            codigo=f.codigo, etiqueta=f.etiqueta, desde=f.desde, hasta=f.hasta,
            color=f.color, prioridad_base=Prioridad(f.prioridad_base),
            accion=f.accion, orden=f.orden, alerta=f.alerta, activo=f.activo,
        )
        for f in filas
    ])

    valores: dict[str, Any] = {}
    for regla in sesion.scalars(
        select(modelo.AlertRule).where(
            modelo.AlertRule.empresa_id == empresa_id,
            modelo.AlertRule.activo.is_(True),
        )
    ):
        valores.update(regla.parametros or {})

    return ConfiguracionCartera(
        empresa_id=empresa_id, buckets=buckets, parametros=Parametros(valores)
    )


def fijar_parametro(
    sesion: Session,
    empresa_id: str,
    codigo_regla: str,
    nombre: str,
    valor: Any,
    usuario_id: str,
) -> None:
    """Cambia un umbral y deja el rastro que exige §10.3.

    Es el camino por el que R01 y R02 se activan: nacen inactivas y se encienden
    solas cuando la empresa les asigna umbral, sin tocar codigo ni desplegar.
    """
    regla = sesion.scalar(
        select(modelo.AlertRule).where(
            modelo.AlertRule.empresa_id == empresa_id,
            modelo.AlertRule.codigo == codigo_regla,
        )
    )
    if regla is None:
        raise LookupError(
            f"No existe la regla '{codigo_regla}' para la empresa '{empresa_id}'."
        )

    parametros = dict(regla.parametros or {})
    anterior = parametros.get(nombre)
    parametros[nombre] = str(valor)
    regla.parametros = parametros

    sesion.add(
        modelo.AuditoriaConfig(
            empresa_id=empresa_id, fecha_hora=datetime.utcnow(),
            usuario_id=usuario_id, entidad=f"ar_alert_rule.{codigo_regla}",
            campo=nombre, valor_anterior=anterior, valor_nuevo=str(valor),
        )
    )
    sesion.flush()
