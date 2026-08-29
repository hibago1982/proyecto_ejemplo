"""Contrato que cumple todo motor de alerta.

La aplicacion es una sola y aloja varios motores (cartera primero, luego los
demas). Lo que los hace intercambiables es este contrato: reciben un contexto de
ejecucion y un conjunto de filas del origen, y devuelven un resultado con la
misma forma. Nada mas es compartido.

Regla de oro de §4.2: el motor es logica pura y sin estado. No abre conexiones,
no escribe en el origen y no consulta el reloj por su cuenta; la fecha de corte
llega en el contexto. Misma entrada, misma salida, siempre. Eso es lo que hace
que los cortes historicos sean reproducibles y que las pruebas sean deterministas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Protocol, Sequence, runtime_checkable

from .alerta import Alerta, Marcador
from .tipos import Fase


@dataclass(frozen=True)
class ContextoEjecucion:
    """Todo lo que el motor necesita saber que no viene en las filas de datos."""

    empresa_id: str
    corte: date
    """Fecha de corte. Es un dato de entrada, nunca `date.today()`."""

    configuracion: Any = None
    """Configuracion propia del motor (buckets, reglas, umbrales)."""

    fase_vigente: Fase = Fase.F1_MOTOR
    """Reglas declaradas para una fase posterior no se evaluan (C-07)."""


@dataclass
class ResultadoMotor:
    """Salida de una corrida. Es lo que se persiste y lo que leen todas las vistas."""

    alertas: list[Alerta] = field(default_factory=list)
    marcadores: list[Marcador] = field(default_factory=list)
    indicadores: dict[str, Any] = field(default_factory=dict)
    reglas_inactivas: dict[str, str] = field(default_factory=dict)
    """Codigo de regla -> por que no se evaluo. Alimenta el aviso de
    'parametros pendientes de definir' de la pantalla de configuracion."""

    def alertas_de(self, sujeto: str) -> list[Alerta]:
        return [a for a in self.alertas if a.sujeto == sujeto]


@runtime_checkable
class MotorAlertas(Protocol):
    """Interfaz que implementa cada motor concreto."""

    codigo: str
    nombre: str

    def evaluar(
        self, contexto: ContextoEjecucion, filas: Iterable[Any]
    ) -> ResultadoMotor: ...


@dataclass
class RegistroMotores:
    """Catalogo de motores disponibles en la aplicacion.

    Existe para que agregar el segundo motor sea registrarlo aqui y no tocar el
    API ni la planificacion de tareas: ambos iteran sobre el registro.
    """

    _motores: dict[str, MotorAlertas] = field(default_factory=dict)

    def registrar(self, motor: MotorAlertas) -> None:
        if motor.codigo in self._motores:
            raise ValueError(f"Ya existe un motor registrado con codigo '{motor.codigo}'")
        self._motores[motor.codigo] = motor

    def obtener(self, codigo: str) -> MotorAlertas:
        try:
            return self._motores[codigo]
        except KeyError:
            disponibles = ", ".join(sorted(self._motores)) or "ninguno"
            raise LookupError(
                f"No hay motor registrado con codigo '{codigo}'. Disponibles: {disponibles}."
            ) from None

    def codigos(self) -> Sequence[str]:
        return tuple(sorted(self._motores))


#: Registro por defecto de la aplicacion.
registro = RegistroMotores()
