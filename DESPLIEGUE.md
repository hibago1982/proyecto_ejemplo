# Montar el motor de alertas en un servidor

Dos caminos. El primero levanta todo con un comando; el segundo instala sobre
un servidor que ya tienes.

Lo que hay que saber antes de empezar: **el motor no inventa umbrales**. R01,
R02 y A12 nacen apagadas y solo se encienden cuando les asignas valor. Es
deliberado (C-05, §16), así que si al primer corte ves «reglas sin evaluar», no
está roto.

---

## Camino 1 · Docker Compose

```bash
cp .env.ejemplo .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # pega el resultado en BUSINT_CLAVE_FIRMA
# y cambia POSTGRES_PASSWORD

cp tu_cartera.xlsx datos/cartera.xlsx     # o configura el ERP en .env
docker compose up --build
```

Levanta PostgreSQL 16, aplica las migraciones, arranca el API en el puerto 8000
y el panel en el 8080.

Después, dentro del contenedor del API:

```bash
docker compose exec api python -m busint_alertas.cli sembrar E01
docker compose exec -e BUSINT_CLAVE_USUARIO=una-clave-larga api \
  python -m busint_alertas.cli usuario crear admin E01 administrador --nombre "Tu nombre"
docker compose exec api python -m busint_alertas.cli ejecutar E01
```

Abre <http://localhost:8080> y entra con ese usuario.

---

## Camino 2 · Instalación directa

Requisitos: Python 3.11 o superior, PostgreSQL 16, y las bibliotecas de sistema
que necesita WeasyPrint para generar el PDF.

```bash
# Debian/Ubuntu
sudo apt install python3-venv postgresql-16 \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
  libcairo2 libgdk-pixbuf-2.0-0 fonts-dejavu-core

sudo -u postgres createuser busint --pwprompt
sudo -u postgres createdb busint_alertas -O busint

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[api,postgres,salidas,programador,planos]"

export BUSINT_DB_URL="postgresql+psycopg://busint:CLAVE@localhost/busint_alertas"
export BUSINT_CLAVE_FIRMA="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export BUSINT_ORIGEN=excel
export BUSINT_ARCHIVO=/ruta/a/cartera.xlsx

alembic upgrade head
python -m busint_alertas.cli sembrar E01
python -m busint_alertas.cli usuario crear admin E01 administrador
python -m busint_alertas.cli ejecutar E01

uvicorn busint_alertas.arranque:app --host 0.0.0.0 --port 8000
```

El panel:

```bash
cd frontend && npm ci && npm run build
# sirve frontend/dist con nginx, y reenvía /api al puerto 8000
# despliegue/nginx.conf sirve de plantilla
```

---

## Variables de entorno

| Variable | Para qué | Obligatoria |
|----------|----------|-------------|
| `BUSINT_DB_URL` | Base del motor | Sí |
| `BUSINT_CLAVE_FIRMA` | Firma los tokens de sesión | Sí |
| `BUSINT_ORIGEN` | `erp`, `excel` o `csv` | No (`erp`) |
| `BUSINT_ERP_URL` | API del ERP | Si el origen es `erp` |
| `BUSINT_ERP_TOKEN` | Token del ERP | No |
| `BUSINT_ARCHIVO` | Ruta del .xlsx o .csv | Si el origen es un archivo |
| `BUSINT_PROGRAMAR` | `1` activa el recálculo diario | No (`0`) |
| `BUSINT_EMPRESAS` | Empresas del recálculo, separadas por coma | Si `BUSINT_PROGRAMAR=1` |
| `BUSINT_HORA_CORTE` | Hora local de Bogotá del recálculo | No (`5`) |

**Si falta `BUSINT_CLAVE_FIRMA` la aplicación se niega a arrancar.** Es a
propósito: una clave por defecto convertiría la firma de los tokens en algo
decorativo, y cualquiera que conociera el código podría emitir sesiones válidas.

---

## Conectar el ERP

El origen por defecto es el API del ERP. El contrato que espera está en
`fuentes/api.py` y es parametrizable, porque el API real de Busint todavía no
está definida:

```
GET {BUSINT_ERP_URL}/cuentas-por-cobrar/abiertas?empresa=E01&corte=2026-08-21&limite=500
Authorization: Bearer {BUSINT_ERP_TOKEN}

{ "datos": [ {…}, {…} ], "siguiente": "…url de la página siguiente… o null" }
```

Los nombres de columna que espera están en `MAPEO_BUSINT`, en
`fuentes/planos.py`. Si el ERP los llama distinto, se ajusta ahí: **es un mapeo,
no código**.

---

## Los cuatro roles

| Rol | Puede |
|-----|-------|
| `consulta` | Leer el panel, la lista, el detalle y exportar |
| `gestor` | Además registrar gestiones de cobranza |
| `coordinador` | Además ejecutar el motor y reprocesar cortes |
| `administrador` | Además modificar umbrales y reglas |

```bash
python -m busint_alertas.cli usuario crear ana E01 gestor --nombre "Ana Restrepo"
```

---

## Encender R01, R02 y A12

Nacen apagadas. Se encienden sin desplegar nada, y cada cambio queda registrado
con usuario, valor anterior y valor nuevo (§10.3):

```bash
python -m busint_alertas.cli umbral E01 R01 umbral_saldo_alto 5000000 --usuario admin
python -m busint_alertas.cli umbral E01 R02 umbral_saldo_critico 20000000 --usuario admin
python -m busint_alertas.cli umbral E01 A12 dias_sin_gestion 30 --usuario admin
```

También desde el panel, en la pantalla de configuración, con un usuario
administrador.

§16 es explícito: **no deduzcas estos montos de la base de demostración.** Los
tiene que fijar la empresa.

---

## Comprobar que quedó bien

```bash
python -m busint_alertas.cli estado E01
curl http://localhost:8000/salud
curl http://localhost:8000/openapi.json | head -c 200
```

Y la suite completa, que necesita `node` para las pruebas de paridad del banco
de pruebas:

```bash
pip install -e ".[dev]" && pytest
```

---

## Qué está probado y qué no

Verificado contra PostgreSQL 16 real antes de entregar este paquete: las cuatro
migraciones, la restricción única de C-17 en el reproceso, los cuatro roles, el
Excel, el PDF, el registro de gestiones y el cierre por ausencia.

**No verificado:** la construcción de las imágenes Docker. El contenedor donde
se preparó este paquete no tiene demonio de Docker. Cada paso que hace el
`Dockerfile` sí se comprobó por separado —los extras de pip resuelven, el
frontend construye, las bibliotecas de WeasyPrint son las que carga— pero el
`docker compose up` no se ha ejecutado nunca. Espera tener que ajustar algo la
primera vez.

**Tampoco verificado:** la conexión al API real del ERP, que no existe todavía.
`FuenteAPI` está probada contra un transporte falso, no contra Busint.

---

## Si algo falla

| Síntoma | Causa probable |
|---------|----------------|
| `Falta la variable BUSINT_CLAVE_FIRMA` | No está en el entorno. Es obligatoria. |
| `La empresa 'E01' no tiene buckets configurados` | Falta `cli sembrar E01` |
| `no tiene ningún corte calculado` | Falta `cli ejecutar E01` |
| Reglas «sin evaluar» en el panel | Correcto: les falta umbral (C-05) |
| El PDF da error 500 | Faltan las bibliotecas de WeasyPrint |
| 401 en todo | El token caducó (12 h). Vuelve a entrar. |
| 403 al cambiar un umbral | Ese usuario no es administrador |
