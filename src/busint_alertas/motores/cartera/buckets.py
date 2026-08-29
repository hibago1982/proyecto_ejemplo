"""Buckets de antiguedad configurables.

§16 exige que los rangos nunca se escriban en el codigo: viven en
`ar_aging_param` y se configuran por empresa. Lo que si es codigo es la mecanica
de asignacion y las invariantes que un conjunto de buckets debe cumplir.

C-14: la especificacion definia cartera vencida como dias > 0, lo que dejaba
"vence hoy" fuera tanto de "por vencer" como de "vencida" y hacia que los
indicadores no sumaran el total. Aqui se declara la identidad explicita:

    cartera total = por vencer + vence hoy + vencida
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ...core.tipos import Prioridad


@dataclass(frozen=True)
class Bucket:
    """Un rango de antiguedad. Los limites son inclusivos en ambos extremos.

    `desde=None` significa sin limite inferior y `hasta=None` sin limite
    superior, que es como se expresan "por vencer" y "mas de 150 dias".
    """

    codigo: str
    etiqueta: str
    desde: int | None
    hasta: int | None
    color: str
    prioridad_base: Prioridad
    accion: str
    orden: int
    activo: bool = True

    def contiene(self, dias: int) -> bool:
        if self.desde is not None and dias < self.desde:
            return False
        if self.hasta is not None and dias > self.hasta:
            return False
        return True

    @property
    def es_por_vencer(self) -> bool:
        return self.hasta is not None and self.hasta < 0

    @property
    def es_vence_hoy(self) -> bool:
        return self.desde == 0 and self.hasta == 0

    @property
    def es_vencida(self) -> bool:
        return self.desde is not None and self.desde > 0


class ConfiguracionBuckets:
    """Conjunto ordenado de buckets de una empresa, validado."""

    def __init__(self, buckets: Sequence[Bucket]) -> None:
        activos = sorted((b for b in buckets if b.activo), key=lambda b: b.orden)
        if not activos:
            raise ValueError("Se requiere al menos un bucket activo.")
        self._validar_cobertura(activos)
        self._buckets = tuple(activos)

    @staticmethod
    def _validar_cobertura(buckets: Sequence[Bucket]) -> None:
        """Los buckets deben cubrir la recta de dias sin huecos ni solapamientos.

        Un hueco deja facturas sin clasificar y un solapamiento las clasifica
        dos veces; ambos se manifestarian como indicadores que no cuadran, que
        es dificil de diagnosticar en produccion. Se detecta al configurar.
        """
        if buckets[0].desde is not None:
            raise ValueError(
                f"El primer bucket '{buckets[0].codigo}' debe abrir sin limite inferior."
            )
        if buckets[-1].hasta is not None:
            raise ValueError(
                f"El ultimo bucket '{buckets[-1].codigo}' debe cerrar sin limite superior."
            )
        for previo, actual in zip(buckets, buckets[1:]):
            if previo.hasta is None:
                raise ValueError(
                    f"El bucket '{previo.codigo}' no tiene limite superior pero no es el ultimo."
                )
            if actual.desde is None:
                raise ValueError(
                    f"El bucket '{actual.codigo}' no tiene limite inferior pero no es el primero."
                )
            if actual.desde != previo.hasta + 1:
                raise ValueError(
                    f"Los buckets '{previo.codigo}' y '{actual.codigo}' dejan un hueco o se "
                    f"solapan: {previo.codigo} termina en {previo.hasta} y "
                    f"{actual.codigo} empieza en {actual.desde}."
                )

    def asignar(self, dias: int) -> Bucket:
        for bucket in self._buckets:
            if bucket.contiene(dias):
                return bucket
        # Inalcanzable: _validar_cobertura garantiza que la recta esta cubierta.
        raise AssertionError(f"Ningun bucket cubre {dias} dias.")

    def obtener(self, codigo: str) -> Bucket:
        for bucket in self._buckets:
            if bucket.codigo == codigo:
                return bucket
        raise LookupError(f"No existe el bucket '{codigo}'.")

    def __iter__(self):
        return iter(self._buckets)

    def __len__(self) -> int:
        return len(self._buckets)
