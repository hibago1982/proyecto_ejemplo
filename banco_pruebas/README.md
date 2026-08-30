# Banco de pruebas del motor

Pagina interactiva para explorar como clasifica el motor: se mueve la fecha de
corte, se cambia la configuracion de umbrales y se ve que alerta dispara cada
factura y por que.

## Por que no reimplementa las reglas

La pagina **no calcula nada**. `generar_banco_pruebas.py` corre el motor real
sobre 96 escenarios (3 configuraciones x 32 cortes) y vuelca su salida a
`datos.json`; `index.html` es un visor de esos resultados.

Reimplementar las reglas en JavaScript habria sido mas facil y mas flexible,
pero duplicaria la logica de alerta, que es exactamente lo que §16 prohibe:
*"no duplicar la logica de alerta en PDF, Excel y pantalla; debe existir una
sola fuente de calculo"*. Y una copia que se desincronice ensena un
comportamiento que el sistema no tiene, que es peor que no tener pagina.

## Regenerar

```bash
python herramientas/generar_banco_pruebas.py   # datos.json desde el motor
python herramientas/armar_banco_pruebas.py     # index.html con los datos dentro
```

La cartera de prueba, los cortes y las configuraciones estan al principio de
`generar_banco_pruebas.py`. Cambiarlos y volver a generar es la forma de probar
otros casos.

## Que cubre

Las 13 facturas y el barrido de cortes hacen disparar el catalogo completo:
A01 a A12 y los marcadores M04 y M05. Incluye ademas dos casos que no generan
alerta y conviene ver:

- **F-109** trae una nota credito sin aplicar, que se netea contra la factura
  mas antigua del cliente (C-10). La tabla muestra el desglose.
- **F-110** tiene saldo negativo: es credito a favor y nunca se clasifica como
  mora (§5.3, caso T09).
