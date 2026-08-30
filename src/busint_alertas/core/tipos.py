"""Vocabulario comun a todos los motores de alerta.

Estos tipos son deliberadamente independientes del dominio de cartera: un motor
de inventario o de tesoreria emite alertas con la misma forma, y por eso viven
aqui y no dentro de `motores/cartera`.
"""

from __future__ import annotations

from enum import Enum


class Prioridad(Enum):
    """Nivel de atencion que exige una alerta.

    El orden numerico permite ordenar la lista de trabajo y quedarse con la
    prioridad mas alta cuando varias reglas afectan a la misma entidad.
    """

    INFORMATIVA = 0
    MEDIA = 1
    ALTA = 2
    MUY_ALTA = 3
    CRITICA = 4

    @property
    def etiqueta(self) -> str:
        return {
            Prioridad.INFORMATIVA: "Informativa",
            Prioridad.MEDIA: "Media",
            Prioridad.ALTA: "Alta",
            Prioridad.MUY_ALTA: "Muy alta",
            Prioridad.CRITICA: "Critica",
        }[self]

    def __lt__(self, otra: "Prioridad") -> bool:
        return self.value < otra.value

    def elevar(self, niveles: int = 1) -> "Prioridad":
        """Sube la prioridad sin pasarse de Critica.

        R01 "eleva la prioridad al menos un nivel": no emite alerta propia,
        agrava la que ya tiene la factura por su antiguedad.
        """
        return Prioridad(min(self.value + niveles, Prioridad.CRITICA.value))


class EstadoAlerta(Enum):
    """Ciclo de vida de una alerta, segun §12.

    §16 lo exige de forma expresa: el estado de la gestion es independiente del
    estado de la factura. Una factura puede seguir vencida y subiendo de bucket
    aunque ya se haya gestionado; GESTIONADA dice que alguien la trabajo, no
    que el cliente haya pagado.

    CERRADA_POR_PAGO se determina por ausencia en el origen, no por un evento
    del ERP (C-18): el motor la marca cuando la entidad deja de aparecer.
    """

    ACTIVA = "activa"
    GESTIONADA = "gestionada"
    CERRADA_POR_PAGO = "cerrada_por_pago"
    CERRADA_MANUAL = "cerrada_manual"

    @property
    def esta_abierta(self) -> bool:
        return self in (EstadoAlerta.ACTIVA, EstadoAlerta.GESTIONADA)


class TipoGestion(Enum):
    """Formas de gestion que §11 enumera."""

    LLAMADA = "llamada"
    CORREO = "correo"
    MENSAJE = "mensaje"
    VISITA = "visita"
    ACUERDO = "acuerdo"
    DISPUTA = "disputa"
    OTRA = "otra"


class Rol(Enum):
    """Los cuatro roles que define C-13, en orden creciente de permisos.

    §8.4 exige que solo usuarios autorizados modifiquen reglas, pero no decia
    que roles existen. Estos son los del analisis:

      * Consulta    - solo lectura.
      * Gestor      - ademas registra gestiones de cobranza.
      * Coordinador - ademas ejecuta el motor y reprocesa cortes.
      * Administrador - ademas modifica parametros y reglas.
    """

    CONSULTA = 0
    GESTOR = 1
    COORDINADOR = 2
    ADMINISTRADOR = 3

    @property
    def etiqueta(self) -> str:
        return {
            Rol.CONSULTA: "Consulta",
            Rol.GESTOR: "Gestor de cartera",
            Rol.COORDINADOR: "Coordinador",
            Rol.ADMINISTRADOR: "Administrador",
        }[self]

    def alcanza(self, minimo: "Rol") -> bool:
        """Si este rol cubre lo que exige `minimo`.

        Los permisos son acumulativos: un administrador puede hacer todo lo que
        hace un gestor. Modelarlo como orden y no como lista de permisos evita
        que anadir un endpoint obligue a tocar cuatro definiciones de rol.
        """
        return self.value >= minimo.value


class Fase(Enum):
    """Fase del plan de desarrollo en la que una regla queda operativa.

    Una regla declarada en una fase posterior a la vigente no se evalua. Es lo
    que evita el problema de C-07: A12 depende del historial de gestion, que no
    existe hasta la fase 5, y evaluarla antes la dispararia siempre.
    """

    F1_MOTOR = 1
    F2_PERSISTENCIA = 2
    F3_API = 3
    F4_PANEL = 4
    F5_GESTION = 5


#: Fase que el sistema tiene desplegada hoy.
#:
#: Existe como constante unica a proposito. Estuvo repetida en tres sitios y se
#: desincronizo: el motor evaluaba A12 mientras el panel la anunciaba como
#: bloqueada por fase. Un usuario habria visto en pantalla que una regla no se
#: evalua mientras sus alertas aparecian en la lista.
FASE_VIGENTE = Fase.F5_GESTION
