"""C-18: cierre de alertas por ausencia."""

from __future__ import annotations

from busint_alertas.core.alerta import Alerta
from busint_alertas.core.tipos import EstadoAlerta, Prioridad
from busint_alertas.motores.cartera.conciliacion import cerrar_por_ausencia

from ..conftest import CORTE, factura


def alerta(nit="900", entidad="F-1", estado=EstadoAlerta.ACTIVA):
    return Alerta(
        codigo="A01",
        etiqueta="Proximo a vencer",
        prioridad=Prioridad.MEDIA,
        accion="Recordar",
        sujeto=nit,
        entidad=entidad,
        estado=estado,
    )


def test_la_factura_que_desaparece_del_origen_se_cierra_por_pago():
    """El ERP solo expone cuentas abiertas: la factura pagada deja de venir."""
    cerradas = cerrar_por_ausencia([alerta(entidad="F-1")], [], CORTE)
    assert len(cerradas) == 1
    assert cerradas[0].estado is EstadoAlerta.CERRADA_POR_PAGO
    assert cerradas[0].datos["fecha_deteccion_pago"] == CORTE


def test_la_factura_que_sigue_abierta_no_se_cierra():
    movs = [factura(dias_vencida=10, numero="F-1", nit="900")]
    assert cerrar_por_ausencia([alerta(entidad="F-1")], movs, CORTE) == []


def test_las_alertas_de_cliente_no_se_cierran_por_ausencia():
    """A10 y A11 se recalculan en cada corrida; no cuelgan de una factura."""
    de_cliente = alerta(entidad=None)
    assert cerrar_por_ausencia([de_cliente], [], CORTE) == []


def test_una_alerta_ya_cerrada_no_se_vuelve_a_cerrar():
    ya_cerrada = alerta(estado=EstadoAlerta.CERRADA_POR_PAGO)
    assert cerrar_por_ausencia([ya_cerrada], [], CORTE) == []


def test_la_misma_factura_de_otro_cliente_no_la_mantiene_abierta():
    """La identidad es cliente + factura, no el numero de factura suelto."""
    movs = [factura(dias_vencida=10, numero="F-1", nit="OTRO")]
    cerradas = cerrar_por_ausencia([alerta(nit="900", entidad="F-1")], movs, CORTE)
    assert len(cerradas) == 1
