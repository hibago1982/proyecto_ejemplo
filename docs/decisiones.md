# Decisiones del analisis, y donde viven en el codigo

Trazabilidad de los 18 hallazgos del documento de arquitectura v2.0 contra la
implementacion. Etapa 1 (motor de reglas) es la unica construida por ahora.

## Contradicciones internas (§3.1)

| ID | Decision adoptada | Donde |
|----|-------------------|-------|
| C-01 | Los dias se calculan contra `fecha_vencimiento`. Campos renombrados a `fecha_emision` / `fecha_vencimiento`. | `motores/cartera/datos.py` · `tests/cartera/test_dias_y_buckets.py` |
| C-02 | R03 usa el operador `>=` (criterio de A10). | `motores/cartera/reglas.py::_r03_facturas_vencidas` |
| C-03 | A01 tiene prioridad Media. Informativa queda para B00 sin alerta activa. | `motores/cartera/reglas.py` · `configuracion.py` (B00) |
| C-04 | R04 y R05 son marcadores de cliente (`M04`, `M05`), no alertas de factura. | `core/alerta.py::Marcador` · `motor.py::_emitir_cliente` |
| C-05 | `pct_mayor_90_umbral` existe como parametro. Sin valor asignado, la regla queda inactiva; el motor no asume ningun defecto. | `core/parametros.py` · `reglas.py::inactiva_porque` |
| C-06 | Parametros renombrados a `dias_preventivos` (R06) y `dias_sin_gestion` (A12), independientes. | `motores/cartera/reglas.py` |
| C-07 | A12 declarada como fase 5. No se evalua antes. | `core/tipos.py::Fase` · `reglas.py` |

## Vacios de definicion (§3.2)

| ID | Decision adoptada | Donde |
|----|-------------------|-------|
| C-08 | `empresa_id` obligatorio en toda fila y aplicado como filtro en el motor, no solo en la consulta. | `datos.py` · `motor.py::_filtrar_empresa` |
| C-09 | COP, `Decimal` con dos decimales, redondeo a pesos solo en presentacion. | `core/dinero.py` |
| C-10 | **Cerrada.** El credito no viene neteado. Es del cliente, no de la fila en que viaja, y se aplica a la factura mas antigua por vencimiento, en cascada. El saldo neto es el que usan las reglas y el que muestra la alerta. | `motores/cartera/creditos.py` · `tests/cartera/test_creditos.py` |
| C-11 | `America/Bogota` como zona del motor. El corte llega como dato, nunca `date.today()`. | `core/fechas.py` · `core/motor.py::ContextoEjecucion` |
| C-12 | **Pendiente de negocio.** `vendedor` y `zona` se transportan en la alerta para soportar cualquiera de las tres reglas de asignacion. | `motor.py` (campo `datos`) |
| C-13 | Roles: fase 8. No implementado. | — |
| C-14 | Identidad explicita `total = por vencer + vence hoy + vencida`, comprobada en pruebas. | `indicadores.py` · `tests/cartera/test_indicadores.py` |
| C-15 | Linea base aceptada. El motor es O(n) sobre las filas y no consulta nada por factura. | `motor.py` |

## Riesgos tecnicos (§3.3)

| ID | Decision adoptada | Donde |
|----|-------------------|-------|
| C-16 | El motor es puro y determinista, que es la precondicion para reproducir un corte pasado. `ar_snapshot` es fase 2. | `motor.py` · `tests/cartera/test_indicadores.py::TestDeterminismo` |
| C-17 | Fase 2 (restriccion unica en base de datos). La clave logica ya esta en la alerta: empresa + corte + sujeto + entidad + regla. | `core/alerta.py` |
| C-18 | Cierre por ausencia implementado como funcion pura, lista para que la fase 2 la invoque. | `motores/cartera/conciliacion.py` |

## Arquitectura de la aplicacion multi-motor

El documento describe el motor de cartera. Como la aplicacion va a alojar varios
motores, `core/` contiene lo que no es de cartera:

- `core/motor.py` — contrato `MotorAlertas`, `ContextoEjecucion`, `ResultadoMotor`
  y el registro de motores. Sumar un motor es crear su paquete y registrarlo.
- `core/alerta.py` — `Alerta`, `Marcador` y `Explicacion`, comunes a cualquier dominio.
- `core/parametros.py` — politica C-05, aplicable a las reglas de cualquier motor.
- `core/tipos.py`, `core/fechas.py`, `core/dinero.py` — vocabulario compartido.

Lo especifico de cartera (buckets, R01–R06, indicadores de §6) vive en
`motores/cartera/` y no es visible desde el nucleo.
