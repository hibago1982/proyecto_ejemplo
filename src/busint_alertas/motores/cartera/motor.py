"""Motor de alertas de cartera. Etapa 1 del plan de desarrollo.

Logica pura y sin estado, segun la regla de oro de §4.2: recibe el corte y las
cuentas abiertas, devuelve el resultado clasificado. No abre conexiones, no
consulta el reloj y no escribe en el origen. Esa disciplina es lo que hace
reproducibles los cortes historicos (C-16) y deterministas las pruebas.

El orden de evaluacion importa y es este:

  1. Aplicar los creditos del cliente a sus facturas mas antiguas (C-10) y
     apartar los saldos que no son deudores (§5.3).
  2. Clasificar cada factura deudora en su bucket y acumular el perfil.
  3. Evaluar las reglas de ambito factura, resolver la elevacion de prioridad
     de R01 y emitir la alerta del bucket mas las de las reglas disparadas.
  4. Evaluar las reglas de ambito cliente sobre el perfil ya completo.
  5. Consolidar la prioridad de cada cliente.

Los creditos van primero porque cambian el saldo, y el saldo alimenta tanto el
aging como los umbrales monetarios. Las reglas de cliente van al final porque
necesitan agregados (n_vencidas, pct_90) que solo existen una vez recorridas
todas las facturas.
"""

from __future__ import annotations

from typing import Iterable

from ...core.alerta import Alerta, Explicacion, Marcador
from ...core.motor import ContextoEjecucion, ResultadoMotor
from ...core.tipos import Prioridad
from .configuracion import ConfiguracionCartera
from .creditos import aplicar_creditos
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

        # --- Paso 1: creditos, antes de cualquier calculo sobre el saldo ---
        movimientos, aplicaciones = aplicar_creditos(movimientos)

        # §5.3 y §10.1: un saldo que no es deudor no se clasifica en el aging.
        # Un saldo negativo es credito a favor, no mora (T09).
        deudores = [m for m in movimientos if m.saldo > 0]
        no_deudores = [m for m in movimientos if m.saldo <= 0]

        perfiles: dict[str, PerfilCliente] = {}
        globales = IndicadoresGlobales()

        # --- Pasos 2 y 3: clasificacion y reglas de factura ---
        reglas_factura = [r for r in activas if r.ambito == Ambito.FACTURA]
        for mov in deudores:
            dias = mov.dias_vencimiento(contexto.corte)
            bucket = config.buckets.asignar(dias)

            perfil = perfiles.setdefault(
                mov.cliente_nit,
                PerfilCliente(cliente_nit=mov.cliente_nit,
                              cliente_nombre=mov.cliente_nombre),
            )
            perfil.acumular(mov.saldo, dias, bucket)
            globales.acumular(mov.saldo, dias, bucket)

            ctx_factura = ContextoFactura(movimiento=mov, dias=dias, bucket=bucket)
            disparadas = [
                (regla, exp)
                for regla in reglas_factura
                if (exp := regla.evaluar(ctx_factura, config.parametros)) is not None
            ]

            # R01 no emite alerta: eleva la prioridad de la que la factura ya
            # tiene por antiguedad. Se resuelve antes de emitir nada, para que
            # la alerta del bucket salga ya con la prioridad final.
            elevaciones = sum(r.eleva_prioridad for r, _ in disparadas)
            prioridad = bucket.prioridad_base.elevar(elevaciones) if elevaciones else bucket.prioridad_base

            datos_comunes = {
                "bucket": bucket.codigo,
                "dias": dias,
                "saldo": mov.saldo,
                "saldo_bruto": mov.saldo_bruto,
                "credito_aplicado": mov.credito_aplicado,
                "vendedor": mov.vendedor,
                "zona": mov.zona,
            }

            if bucket.alerta is not None:
                resultado.alertas.append(
                    Alerta(
                        codigo=bucket.alerta,
                        etiqueta=ETIQUETAS_ALERTA.get(bucket.alerta, bucket.etiqueta),
                        prioridad=prioridad,
                        accion=bucket.accion,
                        sujeto=mov.cliente_nit,
                        entidad=mov.factura,
                        explicacion=Explicacion(
                            regla=bucket.codigo,
                            motivo=f"la factura esta en el rango {bucket.etiqueta}",
                            valor_observado=dias,
                        ),
                        datos={
                            **datos_comunes,
                            "prioridad_base": bucket.prioridad_base.etiqueta,
                            # §7.4: la cadena completa de por que quedo en esta
                            # prioridad, que es lo que hace defendible el semaforo.
                            "elevada_por": [
                                str(e) for r, e in disparadas if r.eleva_prioridad
                            ],
                        },
                    )
                )

            for regla, explicacion in disparadas:
                if regla.alerta is None:
                    continue
                resultado.alertas.append(
                    Alerta(
                        codigo=regla.alerta,
                        etiqueta=ETIQUETAS_ALERTA.get(regla.alerta, regla.etiqueta),
                        prioridad=regla.prioridad,
                        accion=regla.accion,
                        sujeto=mov.cliente_nit,
                        entidad=mov.factura,
                        explicacion=explicacion,
                        datos=dict(datos_comunes),
                    )
                )
                prioridad = max(prioridad, regla.prioridad)

            perfil.prioridad = max(perfil.prioridad, prioridad)


        # --- Paso 4: reglas de cliente, sobre el perfil ya completo ---
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

        # Un cliente cuyo credito cubre toda su cartera se queda sin facturas
        # abiertas y por tanto sin perfil. Su saldo a favor se reporta aparte
        # para que no desaparezca del resultado junto con el.
        a_favor = [
            (a.cliente_nit, a.no_aplicado) for a in aplicaciones if a.no_aplicado > 0
        ]

        globales.n_clientes = len(perfiles)
        resultado.indicadores = {
            "globales": globales.como_dict(),
            "clientes": perfiles,
            "creditos": aplicaciones,
            "creditos_a_favor": a_favor,
            "facturas_saldadas_por_credito": [
                (m.cliente_nit, m.factura, m.saldo_bruto)
                for m in no_deudores
                if m.credito_aplicado > 0
            ],
            # §5.3 exige diferenciar saldo deudor, credito a favor y saldo cero.
            "saldos_no_deudores": [
                (m.cliente_nit, m.factura, m.saldo,
                 "credito_a_favor" if m.saldo < 0 else "saldo_cero")
                for m in no_deudores
            ],
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
