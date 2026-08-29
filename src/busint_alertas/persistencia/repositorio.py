"""Guardar y recuperar el resultado del motor.

Aqui se cumplen los tres riesgos tecnicos de §3.3 del analisis:

C-16. Cada corrida congela el corte en `ar_snapshot`. Reproducir un corte pasado
lee del snapshot y nunca del ERP, porque el ERP solo tiene cuentas abiertas de
hoy: una factura pagada ayer ya no aparece y una abonada muestra otro saldo.

C-17. Toda escritura de alerta es un upsert contra la clave logica, respaldado
por la restriccion unica de la tabla. Reprocesar el mismo corte actualiza, no
duplica.

C-18. El cierre por pago se detecta por ausencia: las alertas activas de un
corte anterior cuya factura ya no aparece se marcan cerradas. Es una
conciliacion, no un evento, porque el ERP no emite ninguno.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.alerta import Alerta as AlertaDominio
from ..core.motor import ResultadoMotor
from ..core.tipos import EstadoAlerta, Prioridad
from ..motores.cartera.configuracion import ConfiguracionCartera
from ..motores.cartera.indicadores import PerfilCliente
from . import modelo
from .modelo import SIN_FACTURA


@dataclass(frozen=True)
class ResumenGuardado:
    """Que hizo la escritura. Alimenta la bitacora de §10.2."""

    alertas_insertadas: int
    alertas_actualizadas: int
    alertas_cerradas: int
    clientes: int
    version_parametros: str


def version_de(config: ConfiguracionCartera) -> str:
    """Huella estable de la configuracion con que se calculo un corte.

    Se guarda junto al snapshot: sin ella, dos cortes calculados con umbrales
    distintos serian indistinguibles y la reproduccion dejaria de ser explicable.
    """
    retrato = {
        "buckets": [
            [b.codigo, b.desde, b.hasta, b.prioridad_base.value, b.alerta]
            for b in config.buckets
        ],
        "parametros": {k: str(v) for k, v in sorted(config.parametros.valores.items())},
    }
    crudo = json.dumps(retrato, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(crudo.encode()).hexdigest()[:32]


class RepositorioCartera:
    """Persiste el resultado de una corrida y lo vuelve a leer."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def guardar(
        self,
        empresa_id: str,
        corte: date,
        resultado: ResultadoMotor,
        config: ConfiguracionCartera,
    ) -> ResumenGuardado:
        """Escribe alertas, riesgo por cliente y snapshot de forma idempotente."""
        version = version_de(config)
        insertadas, actualizadas = self._upsert_alertas(empresa_id, corte, resultado)
        clientes = resultado.indicadores.get("clientes", {})
        self._upsert_riesgo(empresa_id, corte, clientes)
        self._upsert_snapshot(empresa_id, corte, clientes, config, version)
        cerradas = self._cerrar_por_ausencia(empresa_id, corte, resultado)
        self.sesion.flush()
        return ResumenGuardado(
            alertas_insertadas=insertadas,
            alertas_actualizadas=actualizadas,
            alertas_cerradas=cerradas,
            clientes=len(clientes),
            version_parametros=version,
        )

    def _upsert_alertas(
        self, empresa_id: str, corte: date, resultado: ResultadoMotor
    ) -> tuple[int, int]:
        """Inserta o actualiza contra la clave logica de C-17.

        Se resuelve leyendo primero las claves ya presentes en vez de usar el
        upsert nativo del dialecto: mantiene el codigo identico en PostgreSQL y
        SQLite, y el volumen de un corte cabe de sobra en memoria.
        """
        existentes = {
            (a.cliente_nit, a.factura, a.regla): a
            for a in self.sesion.scalars(
                select(modelo.Alerta).where(
                    modelo.Alerta.empresa_id == empresa_id,
                    modelo.Alerta.corte == corte,
                )
            )
        }
        primeros = self._primeros_cortes(empresa_id)

        insertadas = actualizadas = 0
        vistas: set[tuple[str, str, str]] = set()

        for alerta in resultado.alertas:
            clave = (
                alerta.sujeto,
                alerta.entidad or SIN_FACTURA,
                alerta.explicacion.regla if alerta.explicacion else alerta.codigo,
            )
            if clave in vistas:
                # Dos reglas distintas pueden emitir la misma alerta sobre la
                # misma factura; si comparten codigo de regla, es un error del
                # catalogo y no algo que la base deba absorber en silencio.
                raise ValueError(
                    f"El motor emitio dos alertas con la misma clave logica {clave}. "
                    "Revisa el catalogo de reglas."
                )
            vistas.add(clave)

            fila = existentes.get(clave)
            if fila is None:
                fila = modelo.Alerta(
                    empresa_id=empresa_id, corte=corte,
                    cliente_nit=clave[0], factura=clave[1], regla=clave[2],
                    primer_corte=primeros.get(clave[:2], corte),
                )
                self.sesion.add(fila)
                insertadas += 1
            else:
                actualizadas += 1
            self._volcar(fila, alerta)

        return insertadas, actualizadas

    def _primeros_cortes(self, empresa_id: str) -> dict[tuple[str, str], date]:
        """Desde cuando existe la alerta de cada factura.

        Es la referencia de A12 cuando nunca se ha gestionado. Se resuelve en
        una consulta agregada y no una por alerta.
        """
        filas = self.sesion.execute(
            select(
                modelo.Alerta.cliente_nit,
                modelo.Alerta.factura,
                func.min(modelo.Alerta.primer_corte),
            )
            .where(modelo.Alerta.empresa_id == empresa_id)
            .group_by(modelo.Alerta.cliente_nit, modelo.Alerta.factura)
        ).all()
        return {(nit, fac): primer for nit, fac, primer in filas if primer is not None}

    @staticmethod
    def _volcar(fila: modelo.Alerta, alerta: AlertaDominio) -> None:
        datos = dict(alerta.datos)
        fila.codigo = alerta.codigo
        fila.etiqueta = alerta.etiqueta
        fila.prioridad = alerta.prioridad.value
        fila.accion = alerta.accion
        # El estado NO se sobrescribe desde el motor. El motor siempre emite
        # ACTIVA porque no sabe de gestiones; volcar ese valor borraria el
        # trabajo del gestor en cada reproceso. §16 lo exige ademas de forma
        # expresa: el estado de la gestion es independiente del de la factura.
        if fila.estado is None:
            fila.estado = alerta.estado.value
        fila.bucket = datos.get("bucket")
        fila.dias = datos.get("dias")
        fila.saldo = datos.get("saldo")
        fila.saldo_bruto = datos.get("saldo_bruto")
        fila.credito_aplicado = datos.get("credito_aplicado")
        fila.explicacion = str(alerta.explicacion) if alerta.explicacion else None
        fila.datos = json.loads(json.dumps(datos, default=str))
        fila.actualizado = datetime.utcnow()

    def _upsert_riesgo(
        self, empresa_id: str, corte: date, clientes: dict[str, PerfilCliente]
    ) -> None:
        existentes = {
            r.cliente_nit: r
            for r in self.sesion.scalars(
                select(modelo.RiesgoCliente).where(
                    modelo.RiesgoCliente.empresa_id == empresa_id,
                    modelo.RiesgoCliente.corte == corte,
                )
            )
        }
        for nit, perfil in clientes.items():
            fila = existentes.get(nit)
            if fila is None:
                fila = modelo.RiesgoCliente(
                    empresa_id=empresa_id, corte=corte, cliente_nit=nit
                )
                self.sesion.add(fila)
            fila.cliente_nombre = perfil.cliente_nombre
            fila.cartera_total = perfil.cartera_total
            fila.por_vencer = perfil.por_vencer
            fila.vence_hoy = perfil.vence_hoy
            fila.vencida = perfil.vencida
            fila.pct_vencida = perfil.pct_vencida
            fila.mayor_90 = perfil.mayor_90
            fila.pct_90 = perfil.pct_90
            fila.mayor_150 = perfil.mayor_150
            fila.dias_max = perfil.dias_max
            fila.n_facturas = perfil.n_facturas
            fila.n_vencidas = perfil.n_vencidas
            fila.prioridad = perfil.prioridad.value
            fila.marcadores = list(perfil.marcadores)

    def _upsert_snapshot(
        self,
        empresa_id: str,
        corte: date,
        clientes: dict[str, PerfilCliente],
        config: ConfiguracionCartera,
        version: str,
    ) -> None:
        """C-16: congela el corte. Obligatorio, no opcional."""
        existentes = {
            s.cliente_nit: s
            for s in self.sesion.scalars(
                select(modelo.Snapshot).where(
                    modelo.Snapshot.empresa_id == empresa_id,
                    modelo.Snapshot.corte == corte,
                )
            )
        }
        codigos = [b.codigo for b in config.buckets]
        for nit, perfil in clientes.items():
            fila = existentes.get(nit)
            if fila is None:
                fila = modelo.Snapshot(
                    empresa_id=empresa_id, corte=corte, cliente_nit=nit
                )
                self.sesion.add(fila)
            fila.totales_por_bucket = {
                c: str(perfil.por_bucket.get(c, Decimal("0.00"))) for c in codigos
            }
            fila.cartera_total = perfil.cartera_total
            fila.version_parametros = version
            fila.generado = datetime.utcnow()

    def _cerrar_por_ausencia(
        self, empresa_id: str, corte: date, resultado: ResultadoMotor
    ) -> int:
        """C-18: la factura pagada desaparece del ERP; nadie avisa.

        Se comparan las alertas activas del ultimo corte anterior contra las
        facturas presentes en este. Las que ya no estan se cierran por pago.
        """
        anterior = self.sesion.scalar(
            select(modelo.Alerta.corte)
            .where(
                modelo.Alerta.empresa_id == empresa_id,
                modelo.Alerta.corte < corte,
            )
            .order_by(modelo.Alerta.corte.desc())
            .limit(1)
        )
        if anterior is None:
            return 0

        presentes = {
            (a.sujeto, a.entidad)
            for a in resultado.alertas
            if a.entidad is not None
        }
        cerradas = 0
        for fila in self.sesion.scalars(
            select(modelo.Alerta).where(
                modelo.Alerta.empresa_id == empresa_id,
                modelo.Alerta.corte == anterior,
                modelo.Alerta.estado == EstadoAlerta.ACTIVA.value,
                modelo.Alerta.factura != SIN_FACTURA,
            )
        ):
            if (fila.cliente_nit, fila.factura) in presentes:
                continue
            fila.estado = EstadoAlerta.CERRADA_POR_PAGO.value
            fila.detectado_pago = corte
            cerradas += 1
        return cerradas

    # ------------------------------------------------------------------
    # Bitacora
    # ------------------------------------------------------------------

    def abrir_ejecucion(self, empresa_id: str, corte: date) -> modelo.Ejecucion:
        fila = modelo.Ejecucion(
            empresa_id=empresa_id, corte=corte, inicio=datetime.utcnow()
        )
        self.sesion.add(fila)
        self.sesion.flush()
        return fila

    def cerrar_ejecucion(
        self,
        ejecucion: modelo.Ejecucion,
        resumen: ResumenGuardado,
        filas_procesadas: int,
        estado: str = "ok",
        mensaje: str | None = None,
    ) -> None:
        ejecucion.fin = datetime.utcnow()
        ejecucion.filas_procesadas = filas_procesadas
        ejecucion.alertas_generadas = (
            resumen.alertas_insertadas + resumen.alertas_actualizadas
        )
        ejecucion.alertas_cerradas = resumen.alertas_cerradas
        ejecucion.estado = estado
        ejecucion.mensaje = mensaje

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def alertas_del_corte(
        self, empresa_id: str, corte: date, solo_activas: bool = True
    ) -> Sequence[modelo.Alerta]:
        consulta = select(modelo.Alerta).where(
            modelo.Alerta.empresa_id == empresa_id, modelo.Alerta.corte == corte
        )
        if solo_activas:
            consulta = consulta.where(
                modelo.Alerta.estado == EstadoAlerta.ACTIVA.value
            )
        return list(
            self.sesion.scalars(
                consulta.order_by(
                    modelo.Alerta.prioridad.desc(),
                    modelo.Alerta.cliente_nit,
                    modelo.Alerta.factura,
                )
            )
        )

    def riesgo_del_corte(
        self, empresa_id: str, corte: date
    ) -> Sequence[modelo.RiesgoCliente]:
        return list(
            self.sesion.scalars(
                select(modelo.RiesgoCliente)
                .where(
                    modelo.RiesgoCliente.empresa_id == empresa_id,
                    modelo.RiesgoCliente.corte == corte,
                )
                .order_by(
                    modelo.RiesgoCliente.prioridad.desc(),
                    modelo.RiesgoCliente.cartera_total.desc(),
                )
            )
        )

    def snapshot_del_corte(
        self, empresa_id: str, corte: date
    ) -> Sequence[modelo.Snapshot]:
        """C-16: la unica fuente valida para reproducir un corte pasado."""
        return list(
            self.sesion.scalars(
                select(modelo.Snapshot)
                .where(
                    modelo.Snapshot.empresa_id == empresa_id,
                    modelo.Snapshot.corte == corte,
                )
                .order_by(modelo.Snapshot.cliente_nit)
            )
        )

    def cortes_disponibles(self, empresa_id: str) -> Sequence[date]:
        return list(
            self.sesion.scalars(
                select(modelo.Snapshot.corte)
                .where(modelo.Snapshot.empresa_id == empresa_id)
                .distinct()
                .order_by(modelo.Snapshot.corte.desc())
            )
        )
