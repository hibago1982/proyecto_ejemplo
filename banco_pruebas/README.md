# Banco de pruebas del motor

Dos formas de probar el motor. **Dan el mismo resultado**, y hay una prueba que
lo verifica automaticamente.

## 1. `index.html` — pagina publicada, sin instalar nada

Cartera editable, fecha de corte libre y umbrales que se fijan a mano. Se abre y
funciona.

**Lleva dentro un port de las reglas a JavaScript**, y §16 exige una sola fuente
de calculo. Existe por una restriccion concreta: la politica de seguridad de una
pagina publicada permite cargar guiones desde el CDN pero bloquea las peticiones
que Pyodide necesita para traerse su WASM, asi que no se puede ejecutar el
Python real dentro de esa pagina.

Lo que evita que esa copia mienta: `tests/test_paridad_js.py` genera 96
escenarios, los evalua con los dos motores y compara alerta por alerta y cifra
por cifra. Si divergen, la suite falla.

```bash
python herramientas/armar_banco_pruebas.py   # arma index.html
python -m pytest tests/test_paridad_js.py    # verifica la paridad
```

## 2. `herramientas/streamlit_motor.py` — el motor Python real

```bash
pip install -e ".[dev]" streamlit
streamlit run herramientas/streamlit_motor.py
```

Importa `busint_alertas.motores.cartera` directamente. No hay copia de las
reglas, asi que **es la version a la que hay que creerle** si las dos discrepan
alguna vez.

## La cartera de ejemplo

13 facturas de 2 clientes. Moviendo la fecha de corte dispara el catalogo
completo A01–A12 y los marcadores M04 y M05. Incluye dos casos que no generan
alerta y conviene ver funcionando:

- **F-109** trae una nota credito sin aplicar. Se netea contra la factura mas
  antigua del cliente, que es **F-108**, no contra la suya (C-10). La columna
  de rango muestra el desglose.
- **F-110** tiene saldo negativo: es credito a favor y nunca se clasifica como
  mora (§5.3, caso T09).

## Que es cada archivo

| Archivo | Que es |
|---------|--------|
| `motor.js` | Port de las reglas a JavaScript, verificado contra el Python |
| `cartera_ejemplo.js` | La cartera de arranque y los umbrales iniciales |
| `plantilla.html` | La pagina, con `__MOTOR__` y `__CARTERA__` por rellenar |
| `index.html` | Generado. No se edita a mano |
