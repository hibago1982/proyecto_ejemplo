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
| 2. Persistencia (PostgreSQL) | **Completa** — esquema, migraciones, snapshot y cierre por ausencia |
| 3. API (FastAPI) | **Completa** — contrato OpenAPI publicado en `contrato/` |
| 4. Panel de control | **Completo** — React + Vite contra el API real |
| 5. Lista de gestión y detalle | **Completa** — bandeja priorizada, filtros, búsqueda y ficha de cliente |
| 6. Gestión y compromisos | **Completa** — registro, estados, compromisos y A12 activa |
| 7. Salidas formales | **Completa** — PDF y Excel desde el mismo resultado persistido |
| 8. Auditoría y despliegue | **Completa** — roles, autenticación, ejecución programada |

## Estructura

    src/busint_alertas/
      core/          # comun a todos los motores: contrato, alerta, parametros, dinero, fechas
      fuentes/       # origenes de datos: Excel, CSV, API REST del ERP
      persistencia/  # esquema PostgreSQL, repositorio, configuracion en base
      api/           # FastAPI: panel, gestion, detalle, configuracion, ejecucion
      motores/
        cartera/     # buckets, reglas R01-R06, indicadores de §6, conciliacion
      ejecucion.py   # corrida completa: leer, evaluar, persistir
    migraciones/     # Alembic
    contrato/        # openapi.json versionado, fuente de los tipos del frontend
    frontend/        # React 18 + Vite + Tailwind + TanStack Query + Recharts
    herramientas/    # generar_contrato.py, servidor_demo.py
    tests/
      datos/         # archivo de prueba sintetico de BUSINT (30 NIT, 120 facturas)
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

## Persistencia

PostgreSQL 16. El esquema son las entidades de §6.2, con tres piezas que
resuelven los riesgos tecnicos del analisis:

- **`ar_alerta` lleva restriccion unica** sobre empresa + corte + cliente +
  factura + regla (C-17). Reprocesar un corte actualiza, no duplica. Las
  alertas de cliente guardan cadena vacia en `factura` y no NULL, porque en SQL
  dos NULL no son iguales y la restriccion dejaria pasar duplicados.
- **`ar_snapshot` es obligatoria** (C-16). Cada corrida congela el corte con su
  huella de parametros. Reproducir un corte pasado lee de ahi, nunca del ERP,
  que solo tiene cuentas abiertas de hoy.
- **Cierre por ausencia** (C-18). Las alertas activas cuya factura ya no
  aparece se marcan cerradas por pago. Es una conciliacion, no un evento: el
  ERP no emite ninguno.

```bash
export BUSINT_DB_URL="postgresql+psycopg://usuario:clave@host/busint_alertas"
alembic upgrade head
```

Los buckets y umbrales viven en `ar_aging_param` y `ar_alert_rule`, no en el
codigo (§8.4 y §16). Cambiar un umbral es un UPDATE con rastro en
`ar_auditoria_config`, y es asi como R01 y R02 se activan: nacen inactivas y se
encienden cuando la empresa les asigna valor, sin desplegar nada.

```python
from busint_alertas.ejecucion import ejecutar_corte
from busint_alertas.persistencia import fijar_parametro

fijar_parametro(sesion, "E01", "R01", "umbral_saldo_alto", 5_000_000, "hbarrera")
corrida = ejecutar_corte(sesion, fuente, "E01", date(2026, 8, 21))
```

## API

FastAPI. El contrato OpenAPI se publica en `contrato/openapi.json` y esta
versionado a proposito: un cambio incompatible aparece como diferencia en la
revision de codigo en vez de descubrirse cuando el frontend falla. Una prueba
falla si el contrato se queda atras del codigo.

```bash
pip install -e ".[api,bd,planos]"
uvicorn --factory 'mi_arranque:app'   # ver crear_app en api/app.py
python herramientas/generar_contrato.py
npx openapi-typescript contrato/openapi.json -o src/api/tipos.ts   # frontend
```

| Endpoint | Seccion |
|----------|---------|
| `GET /api/v1/panel` | §8.1 KPIs, aging y ranking en una sola respuesta |
| `GET /api/v1/gestion` | §8.2 bandeja filtrable y ordenable, con paginacion |
| `GET /api/v1/clientes/{nit}` | §8.3 indicadores y alertas del cliente |
| `GET /api/v1/configuracion` | §8.4 buckets, reglas y umbrales pendientes |
| `PUT /api/v1/configuracion/reglas/{codigo}/parametros/{nombre}` | Fijar un umbral, con auditoria |
| `POST /api/v1/ejecucion` | §10.2 corrida manual y reproceso |
| `GET /api/v1/cortes` | Cortes disponibles para el selector de fecha |

**Los montos viajan como cadena, no como numero.** JSON no tiene decimales
exactos y un `float` de JavaScript no representa 1234567.89 sin error; C-09
exige conservar los dos decimales en el calculo y en la auditoria, y
serializarlos como cadena es lo unico que lo garantiza de extremo a extremo.
Hay una prueba que falla si algun monto se declara `number` en el contrato.

**Autenticación y roles.** `POST /api/v1/sesion` devuelve un token firmado; el
resto de endpoints lo esperan en `Authorization: Bearer`. La empresa y el rol
van dentro del token, así que no se pueden cambiar sin invalidar la firma.

Los cuatro roles de C-13 son acumulativos, y cada endpoint declara su suelo:

| Rol | Puede |
|-----|-------|
| Consulta | Leer el panel, la lista, el detalle y exportar |
| Gestor de cartera | Además registrar gestiones |
| Coordinador | Además ejecutar el motor y reprocesar cortes |
| Administrador | Además modificar umbrales y reglas |

```bash
export BUSINT_CLAVE_FIRMA="..."   # sin ella el API se niega a emitir tokens
```

## Pantallas

![Panel de cartera](panel.png)

Tres pantallas, cada una con dirección propia en el hash de la URL para que un
gestor pueda pasarle a su coordinador el enlace de un cliente en vez de
explicarle cómo llegar:

| Ruta | Pantalla |
|------|----------|
| `#/` | Panel de control (§8.1) |
| `#/gestion` | Lista de gestión (§8.2) |
| `#/clientes/{nit}` | Detalle del cliente (§8.3) |

![Lista de gestión](lista.png)

![Detalle del cliente con gestión](gestion.png)

El detalle permite registrar una gestión y muestra el historial de cobranza con
sus compromisos de pago. Registrar una gestión **no toca el saldo ni el bucket**:
§16 separa el estado de la gestión del de la factura, porque una factura sigue
vencida aunque ya se haya gestionado.

Cada alerta puede explicar por qué se disparó: la regla, el parámetro vigente y
el valor que la disparó (§7.4). El texto llega hecho del motor; componerlo en el
navegador sería reimplementar la regla donde nadie la prueba.

React 18 + TypeScript + Vite, con Tailwind para el sistema de diseño de §7.2,
TanStack Query para la caché y Recharts para el aging. Los tipos no se escriben
a mano: salen de `contrato/openapi.json`, de modo que un cambio incompatible en
el backend rompa la compilación del frontend en vez de fallar en silencio.

```bash
cd frontend
npm install
npm run tipos     # regenera src/api/tipos.ts desde el contrato
npm run dev       # proxy a http://localhost:8000
npm test
```

Para verlo funcionando de extremo a extremo con el archivo de prueba:

```bash
python herramientas/servidor_demo.py   # API en :8000 con el corte ya calculado
cd frontend && npm run dev             # panel en :5173
```

**En el frontend no hay lógica de negocio.** Los porcentajes, las prioridades y
los colores de aging llegan calculados del API. Recalcular cualquiera de ellos
en el navegador sería una segunda implementación que podría divergir del PDF y
del Excel, que es justo lo que §16 prohíbe al exigir una sola fuente de cálculo.

## Salidas formales

`GET /api/v1/exportar/excel` y `/exportar/pdf`. Ambas leen del mismo resultado
persistido que la pantalla, que es la única forma de cumplir §13: *"el PDF y
Excel muestran exactamente la misma clasificación que la pantalla para el mismo
corte"*. Hay pruebas que comparan las tres cifra a cifra.

El Excel trae cuatro hojas —alertas, riesgo por cliente, aging y parámetros— con
las columnas de auditoría que pide §9: código de alerta, prioridad, días,
explicación y el desglose de saldo bruto menos crédito aplicado. El PDF se
genera desde HTML con WeasyPrint, así que reutiliza el sistema de diseño de la
pantalla en vez de mantener dos maquetaciones.

## Ejecución programada

```python
from busint_alertas.planificador import Programacion, crear_planificador

crear_planificador(Programacion(fabrica, fuente, empresas=["E01"], hora=5))
```

APScheduler a las 05:00 de America/Bogotá (C-11). La corrida programada llama a
la **misma** función que el botón de reproceso manual: que no existan dos
caminos es lo que evita que el corte nocturno dé un resultado distinto al que se
ve en pantalla. Un fallo en una empresa no detiene a las demás, y queda en
`ar_ejecucion`.

## Banco de pruebas

Dos formas de probar el motor sin levantar el sistema entero. Dan el mismo
resultado, y hay una prueba que lo verifica.

**Sin instalar nada** — `banco_pruebas/index.html`: cartera editable, fecha de
corte libre, umbrales a mano. Lleva dentro un port de las reglas a JavaScript,
porque la política de seguridad de una página publicada impide ejecutar Python
en ella. `tests/test_paridad_js.py` evalúa 96 escenarios con los dos motores y
compara alerta por alerta; si divergen, la suite falla.

**Sobre el motor Python real** — `herramientas/streamlit_motor.py`:

```bash
pip install -e ".[dev]" streamlit
streamlit run herramientas/streamlit_motor.py
```

Importa `busint_alertas.motores.cartera` directamente, así que es la versión a
la que hay que creerle si las dos discrepan. Detalles en
`banco_pruebas/README.md`.

## Probarlo entero

```bash
python herramientas/servidor_demo.py   # API en :8000, corte ya calculado
cd frontend && npm run dev             # panel en :5173
```

Usuarios de demostración, uno por rol: `consulta`, `gestor`, `coordinador`,
`admin`, todos con clave `demo1234`.

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
