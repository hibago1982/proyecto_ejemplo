# BUSINT — Motores de alerta

Aplicacion unica que aloja varios motores de alerta. El primero es el **motor de
alertas de cartera**; los siguientes se suman registrandose en el nucleo comun.

Base: *Especificacion Funcional v1.0 (17/08/2026)* y *Analisis tecnico y
arquitectura de desarrollo v2.0 (23/08/2026)*, que la corrige.

## Estado

**Etapa 1 del plan de §8: motor de reglas.** Logica pura, sin base de datos y sin
API, que es como el documento recomienda empezar: es la unica parte que no
depende de decisiones de infraestructura pendientes.

| Etapa | Estado |
|-------|--------|
| 0. Contrato de datos | Parcial — mapeo del archivo plano cerrado; falta validar C-10 y el modelo SQL |
| 1. Motor de reglas | **Completo** — las 6 reglas de §5.4, el catalogo A01–A12, T01–T12 y la reconciliacion |
| 2. Persistencia (PostgreSQL) | Pendiente |
| 3. API (FastAPI) | Pendiente |
| 4–8 | Pendiente |

## Estructura

    src/busint_alertas/
      core/        # comun a todos los motores: contrato, alerta, parametros, dinero, fechas
      fuentes/     # origenes de datos: Excel, CSV, API REST del ERP
      motores/
        cartera/   # buckets, reglas R01-R06, indicadores de §6, conciliacion
    tests/
      datos/       # archivo de prueba sintetico de BUSINT (30 NIT, 120 facturas)
    docs/
      decisiones.md   # los 18 hallazgos C-01..C-18 y donde vive cada uno
      pendientes.md   # que falta para cerrar la etapa 1

## Origenes de datos

El motor no sabe de donde vienen los datos. Todas las fuentes cumplen el mismo
contrato y producen `Movimiento`, asi que se prueba contra un archivo y se
despliega contra el ERP con la misma logica (§4.3: "lo unico que cambia es el
conector de datos").

```python
from busint_alertas.fuentes import FuenteExcel, FuenteCSV, FuenteAPI, MAPEO_BUSINT

fuente = FuenteExcel("cartera.xlsx")                       # exportacion del ERP
fuente = FuenteCSV("cartera.csv", MAPEO_BUSINT)            # archivo delimitado
fuente = FuenteAPI("https://erp.busint.co/api",            # API del ERP
                   MAPEO_BUSINT, token=os.environ["ERP_TOKEN"])

movimientos = fuente.leer(empresa_id="E01", corte=date(2026, 8, 21))
```

Los nombres de columna viven en un `MapeoCampos`, no en el codigo: adaptar el
motor a otro ERP o a un cambio de nombre es editar un mapeo. La lectura SQL
directa sobre el MySQL de Busint es fase 2.

## Uso

```python
from datetime import date
from decimal import Decimal

from busint_alertas.core.motor import ContextoEjecucion
from busint_alertas.motores.cartera import ConfiguracionCartera, MotorCartera, Movimiento

config = ConfiguracionCartera.plantilla(
    "E01",
    dias_preventivos=15,
    n_facturas_vencidas=3,
    pct_mayor_90_umbral=Decimal("40"),
    # Sin estos dos, R01 y R02 quedan inactivas (C-05 y §16).
    umbral_saldo_alto=Decimal("5000000"),
    umbral_saldo_critico=Decimal("20000000"),
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
