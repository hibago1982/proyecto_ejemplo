# Pendientes para cerrar la etapa 1

## A. Documentos que faltan

El documento de arquitectura v2.0 corrige la **Especificacion Funcional v1.0**
pero no la reemplaza. Estas partes se citan y no llegaron:

| Falta | Para que se necesita | Estado en el codigo |
|-------|----------------------|---------------------|
| §5.4 — condicion de R01, R02, R04 y R05 | Son 4 de las 6 reglas del motor | Declaradas sin evaluador; inactivas y visibles como pendientes |
| §5.2 — rangos y paleta de aging | Limites reales de los buckets | Plantilla propuesta en `configuracion.py`, coherente con los cortes de 90 y 150 de §6 |
| §7 — catalogo completo A01–A12 | Etiquetas y a que regla pertenece cada alerta | Solo A01, A10, A11 y A12 tienen etiqueta |
| §14 — casos T01–T12 | Es el entregable verificable de la etapa 1 segun §8 | 59 pruebas propias cubren lo que este documento determina |
| Archivo de prueba (120 facturas / 30 NIT) | Reconciliacion exigida por §8 etapa 1 | Sin hacer |

## B. Decisiones de negocio (§9 del documento)

Las ocho decisiones del documento siguen abiertas. Estas tres afectan el motor y
no dependen de infraestructura, asi que son las primeras:

1. **C-10 — ¿el saldo abierto del ERP ya viene neto de notas credito y abonos?**
   El documento la marca como la mas urgente. Hoy el motor usa `saldo` tal como
   llega y transporta `valor_credito` sin restarlo. Si la respuesta es que no
   viene neto, cambia la definicion de saldo deudor y con ella todos los
   indicadores.
2. **Umbrales reales** de R01, R02, `n_facturas_vencidas`, `dias_preventivos` y
   `pct_mayor_90_umbral`. Mientras no los fije la empresa, esas reglas quedan
   inactivas por diseno (C-05).
3. **C-12 — regla de asignacion del responsable**: por vendedor, por zona o
   manual. Ambos campos ya viajan en la alerta, asi que es configuracion, no
   cambio de modelo.

## C. Preguntas que surgieron al implementar

Ninguna estaba en el documento; aparecieron al escribir el codigo.

1. **¿R06 debe disparar tambien el dia del vencimiento?** Hoy la ventana es
   `-dias_preventivos <= dias <= 0`, es decir incluye "vence hoy". La lectura
   alternativa (`< 0`, estrictamente por vencer) dejaria el dia del vencimiento
   sin alerta, lo que parece indeseable en operacion. Confirmar.
2. **¿A10 es alerta de cliente o se replica en cada factura vencida?** R03
   evalua una condicion del cliente. Se implemento como una alerta de cliente
   (`entidad=None`). Si la lista de gestion debe mostrarla por factura, cambia.
3. **¿A11 tiene codigo de regla propio?** El documento la asocia a un umbral
   pero no le asigna un R0x. Se registro con el codigo de la alerta.
4. **¿El operador de A11 es `>` o `>=`?** El documento dice "supera un umbral",
   que se leyo como estrictamente mayor. R03 usa `>=` por C-02; conviene que la
   diferencia sea deliberada y no accidental.
5. **¿Que pasa con una factura de saldo cero o negativo?** El motor la procesa
   sin excepcion. Si el ERP puede entregarlas, hay que decidir si se excluyen.

## D. Nota tecnica

El documento fija Python 3.12. El proyecto declara `>=3.11` porque es lo
disponible en el entorno actual; el codigo no usa nada exclusivo de 3.12.
