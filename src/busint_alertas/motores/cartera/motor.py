"""Motor de alertas de cartera. Etapa 1 del plan de desarrollo.

Logica pura y sin estado, segun la regla de oro de §4.2: recibe el corte y las
cuentas abiertas, devuelve el resultado clasificado. No abre conexiones, no
consulta el reloj y no escribe en el origen. Esa disciplina es lo que hace
reproducibles los cortes historicos (C-16) y deterministas las pruebas.

El orden de evaluacion importa y es este:

  1. Clasificar cada factura en su bucket y acumular el perfil del cliente.
  2. Evaluar las reglas de ambito factura sobre cada factura.
  3. Evaluar las reglas de ambito cliente sobre el perfil ya completo.
  4. Consolidar la prioridad de cada cliente.

Las reglas de cliente van despues porque necesitan agregados (n_vencidas, pct_90)
que solo existen una vez recorridas todas las facturas.
"""

from __future__ import annotations

from typing import Iterable

from ...core.alerta import Alerta, Marcador
from ...core.motor import ContextoEjecucion, ResultadoMotor
from ...core.tipos import Prioridad
from .configuracion import ConfiguracionCartera
from .datos import Movimiento
from .indicadores import IndicadoresGlobales, PerfilCliente
from .reglas import (
    ETIQUETAS_ALERTA,
    ETIQUETAS_MARCADOR,
    REGLAS,
    Ambito,
    ContextoCliente,
    ContextoFactura,
    DefinicionRegla,
)


class MotorCartera:
    """Implementa el contrato `MotorAlertas` para el dominio de cartera."""

    codigo = "cartera"
    nombre = "Motor de alertas de cartera"

    def evaluar(
        self, contexto: ContextoEjecucion, filas: Iterable[Movimiento]
    ) -> ResultadoMotor:
        config = contexto.configuracion
        if not isinstance(config, ConfiguracionCartera):
            raise TypeError(
                "El motor de cartera requiere una ConfiguracionCartera en el contexto."
            )

        movimientos = self._filtrar_empresa(filas, contexto.empresa_id)
        resultado = ResultadoMotor()
        activas, resultado.reglas_inactivas = self._separar_reglas(config, contexto)

        perfiles: dict[str, PerfilCliente] = {}
        globales = IndicadoresGlobales()

        # --- Paso 1 y 2: clasificacion y reglas de factura ---
        reglas_factura = [r for r in activas if r.ambito == Ambito.FACTURA]
        for mov in movimientos:
            dias = mov.dias_vencimiento(contexto.corte)
            bucket = config.buckets.asignar(dias)

            perfil = perfiles.setdefault(
                mov.cliente_nit,
                PerfilCliente(cliente_nit=mov.cliente_nit,
                              cliente_nombre=mov.cliente_nombre),
            )
            perfil.acumular(mov.saldo, dias, bucket)
            globales.acumular(mov.saldo, dias, bucket)

            prioridad_factura = bucket.prioridad_base
            ctx_factura = ContextoFactura(movimiento=mov, dias=dias, bucket=bucket)

            for regla in reglas_factura:
                explicacion = regla.evaluar(ctx_factura, config.parametros)
                if explicacion is None:
                    continue
                resultado.alertas.append(
                    Alerta(
                        codigo=regla.alerta or regla.codigo,
                        etiqueta=ETIQUETAS_ALERTA.get(
                            regla.alerta or regla.codigo, regla.etiqueta
                        ),
                        prioridad=regla.prioridad,
                        accion=regla.accion,
                        sujeto=mov.cliente_nit,
                        entidad=mov.factura,
                        explicacion=explicacion,
                        datos={
                            "bucket": bucket.codigo,
                            "dias": dias,
                            "saldo": mov.saldo,
                            "vendedor": mov.vendedor,
                            "zona": mov.zona,
                        },
                    )
                )
                prioridad_factura = max(prioridad_factura, regla.prioridad)

            perfil.prioridad = max(perfil.prioridad, prioridad_factura)

        # --- Paso 3: reglas de cliente, sobre el perfil ya completo ---
        reglas_cliente = [r for r in activas if r.ambito == Ambito.CLIENTE]
        for nit, perfil in perfiles.items():
            ctx_cliente = ContextoCliente(
                cliente_nit=nit,
                cartera_total=perfil.cartera_total,
                vencida=perfil.vencida,
                pct_vencida=perfil.pct_vencida,
                mayor_90=perfil.mayor_90,
                pct_90=perfil.pct_90,
                mayor_150=perfil.mayor_150,
                dias_max=perfil.dias_max,
                n_vencidas=perfil.n_vencidas,
            )
            for regla in reglas_cliente:
                explicacion = regla.evaluar(ctx_cliente, config.parametros)
                if explicacion is None:
                    continue
                self._emitir_cliente(resultado, perfil, regla, explicacion)
                perfil.prioridad = max(perfil.prioridad, regla.prioridad)

        globales.n_clientes = len(perfiles)
        resultado.indicadores = {
            "globales": globales.como_dict(),
            "clientes": perfiles,
        }
        return resultado

    # ------------------------------------------------------------------

    @staticmethod
    def _filtrar_empresa(
        filas: Iterable[Movimiento], empresa_id: str
    ) -> list[Movimiento]:
        """C-08: el aislamiento por empresa se aplica en el motor, no solo en la consulta.

        Es una red de seguridad: si el conector del ERP trae de mas, el motor no
        mezcla empresas en el mismo corte.
        """
        return [m for m in filas if m.empresa_id == empresa_id]

    @staticmethod
    def _separar_reglas(
        config: ConfiguracionCartera, contexto: ContextoEjecucion
    ) -> tuple[list[DefinicionRegla], dict[str, str]]:
        activas: list[DefinicionRegla] = []
        inactivas: dict[str, str] = {}
        for regla in REGLAS:
            motivo = regla.inactiva_porque(config.parametros, contexto.fase_vigente)
            if motivo is None:
                activas.append(regla)
            else:
                inactivas[regla.codigo] = motivo
        return activas, inactivas

    @staticmethod
    def _emitir_cliente(
        resultado: ResultadoMotor,
        perfil: PerfilCliente,
        regla: DefinicionRegla,
        explicacion,
    ) -> None:
        """Emite alerta o marcador segun lo que declare la regla (C-04)."""
        if regla.marcador is not None:
            resultado.marcadores.append(
                Marcador(
                    codigo=regla.marcador,
                    etiqueta=ETIQUETAS_MARCADOR.get(regla.marcador, regla.etiqueta),
                    sujeto=perfil.cliente_nit,
                    explicacion=explicacion,
                )
            )
            perfil.marcadores.append(regla.marcador)
            return

        codigo = regla.alerta or regla.codigo
        resultado.alertas.append(
            Alerta(
                codigo=codigo,
                etiqueta=ETIQUETAS_ALERTA.get(codigo, regla.etiqueta),
                prioridad=regla.prioridad,
                accion=regla.accion,
                sujeto=perfil.cliente_nit,
                entidad=None,
                explicacion=explicacion,
                datos={
                    "cartera_total": perfil.cartera_total,
                    "vencida": perfil.vencida,
                    "n_vencidas": perfil.n_vencidas,
                },
            )
        )
