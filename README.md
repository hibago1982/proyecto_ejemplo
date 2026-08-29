# BUSINT — Motores de alerta

Aplicacion unica que aloja varios motores de alerta. El primero es el **motor de
alertas de cartera**; los siguientes se suman registrandose en el nucleo comun.

Base: *BUSINT — Motor de Alertas de Cartera, analisis tecnico y arquitectura de
desarrollo, v2.0 (23/08/2026)*.

## Estado

**Etapa 1 del plan de §8: motor de reglas.** Logica pura, sin base de datos y sin
API, que es como el documento recomienda empezar: es la unica parte que no
depende de decisiones de infraestructura pendientes.

| Etapa | Estado |
|-------|--------|
| 0. Contrato de datos | Parcial — falta cerrar C-10 y el mapeo contra Busint |
| 1. Motor de reglas | **En curso** — 2 de 6 reglas con logica definida |
| 2. Persistencia (PostgreSQL) | Pendiente |
| 3. API (FastAPI) | Pendiente |
| 4–8 | Pendiente |

## Estructura

    src/busint_alertas/
      core/        # comun a todos los motores: contrato, alerta, parametros, dinero, fechas
      motores/
        cartera/   # buckets, reglas R01-R06, indicadores de §6, conciliacion
    tests/
    docs/
      decisiones.md   # los 18 hallazgos C-01..C-18 y donde vive cada uno
      pendientes.md   # que falta para cerrar la etapa 1

## Uso

```python
from datetime import date
from decimal import Decimal

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import ConfiguracionCartera, MotorCartera, Movimiento

config = ConfiguracionCartera.plantilla(
    "E01",
    dias_preventivos=5,
    n_facturas_vencidas=3,
    pct_mayor_90_umbral=Decimal("40"),
)

contexto = ContextoEjecucion(empresa_id="E01", corte=date(2026, 8, 31), configuracion=config)
resultado = MotorCartera().evaluar(contexto, movimientos)

for alerta in resultado.alertas:
    print(alerta.codigo, alerta.sujeto, alerta.explicacion)

# Reglas que no se evaluaron, y por que
print(resultado.reglas_inactivas)
```

## Pruebas

```bash
pip install -e ".[dev]"
pytest
```

## Dos principios que conviene no perder

**El motor no asume valores por defecto.** Una regla cuyo umbral la empresa no ha
configurado queda inactiva y se reporta en `reglas_inactivas`. Un umbral inventado
por el programador produce alertas que nadie puede defender (C-05).

**Toda alerta explica por que existe.** Cada una lleva la regla, el parametro
vigente y el valor que la disparo. Esa cadena se calcula en el motor, no en la
pantalla, porque armarla en el frontend seria una segunda implementacion de la
regla y contradice la fuente unica de calculo de §16.
