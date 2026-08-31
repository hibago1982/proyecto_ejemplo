# Pendientes para cerrar la etapa 1

## A. Estado de la especificacion

Con la Especificacion Funcional v1.0 ya no falta ninguna definicion de reglas.
Lo que cerro:

| Antes faltaba | Como quedo |
|---------------|------------|
| §5.4 — condicion de R01, R02, R04 y R05 | Las seis reglas implementadas con su condicion literal |
| §5.2 — colores y prioridades de aging | Tomados de la especificacion, no inventados. Aparece el nivel "Muy alta" |
| §7 — catalogo A01–A12 | Completo. A02–A08 las emiten los buckets, que antes no emitian nada |
| §14 — casos T01–T12 | `tests/cartera/test_casos_t01_t12.py`, con el enunciado literal de cada uno |
| §5.3 — saldos negativos | El motor diferencia saldo deudor, credito a favor y saldo cero |

Correcciones que la especificacion obligo a hacer sobre lo que se habia supuesto:

- **R06 no cubre el dia del vencimiento.** La ventana preventiva es
  estrictamente `dias < 0`; el dia del vencimiento es A02 con prioridad Alta.
  §7 los separa y §14 lo confirma con T01 y T02. Antes se habia incluido
  `dias = 0` en la ventana, que era una suposicion y era incorrecta.
- **Faltaban las alertas de bucket.** A02–A08 no existian: el motor clasificaba
  en buckets pero no emitia alerta por antiguedad, y §13 lo exige de forma
  literal ("una factura con 1-30 dias recibe A03").
- **R01 no emite alerta.** Su efecto es elevar la prioridad al menos un nivel,
  no generar una alerta propia. Por eso no tiene entrada en el catalogo §7.
- **Faltaba el nivel "Muy alta"** entre Alta y Critica.
- **Los colores y prioridades de los buckets** eran invencion propia. Ahora son
  los de §5.2.

## A-bis. Estado al cerrar las ocho etapas

Las ocho etapas del plan de §8 estan implementadas. Lo que queda abierto no es
codigo por escribir, sino decisiones y verificaciones que no pueden hacerse
desde aqui:

| Pendiente | Por que sigue abierto |
|-----------|----------------------|
| ~~PostgreSQL nunca se ha ejecutado~~ | **Cerrado.** Verificado contra PostgreSQL 16.13: las cuatro migraciones, JSONB en las cuatro columnas, el indice GIN, las nueve politicas de seguridad por fila, el rol, la restriccion unica de C-17 en el reproceso, los roles, el Excel, el PDF y el registro de gestiones. Aparecieron dos defectos: el rol se creaba sin condicion y rompia en cualquier segunda base del mismo cluster, y dos columnas JSON quedaron sin convertir a JSONB. |
| **Las imagenes Docker no se han construido** | El contenedor donde se preparo el paquete no tiene demonio de Docker. Cada paso del `Dockerfile` se verifico por separado, pero `docker compose up` no se ha ejecutado nunca. |
| **Umbrales monetarios reales** | R01 y R02 se activan solas cuando la empresa los fije. §16 prohibe deducirlos de la base de demostracion. |
| **`dias_sin_gestion` de A12** | Igual: la regla ya funciona, le falta el valor. |
| **C-10 contra datos reales** | La logica de notas credito nunca se ha corrido contra un extracto que las traiga; el archivo de prueba tiene la columna en cero. |
| **Alta de usuarios** | Se crean por codigo. Falta la pantalla de administracion de usuarios. |
| **Revocacion de tokens** | Un token robado vale hasta que caduca (12 h). Si eso no basta, hace falta una lista de revocacion. |

## B. Decisiones de negocio (§9 del documento)

Las ocho decisiones del documento siguen abiertas. Estas tres afectan el motor y
no dependen de infraestructura, asi que son las primeras:

1. ~~**C-10 — notas credito y abonos.**~~ **Cerrada por decision de negocio:**
   el saldo no viene neteado; el credito se aplica a la factura mas antigua y
   el saldo neto es el que lleva la alerta. Implementado en `creditos.py`.
   Queda pendiente **validar contra el modelo real** que `Valor Credito` es
   efectivamente un credito del cliente sin aplicar: el archivo de prueba no lo
   ejerce (es 0 en las 120 filas), asi que la logica no se ha corrido nunca
   contra un caso real.
2. **Umbrales reales** de `umbral_saldo_alto` (R01), `umbral_saldo_critico`
   (R02), `n_facturas_vencidas`, `dias_preventivos` y `pct_mayor_90_umbral`.
   Mientras no los fije la empresa, esas reglas quedan inactivas por diseno
   (C-05). §16 lo refuerza: no usar la base de demostracion para fijar
   umbrales monetarios reales.
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
6. **¿R02 es de factura o de cliente?** Se implemento de factura: §5.4 usa la
   misma palabra "saldo" para R01 y R02, y R01 es inequivocamente de factura
   por su condicion de dias. T11 lo respalda, aunque con una sola factura no
   distingue entre las dos lecturas. Si "exposicion alta" se refiere a la
   exposicion total del cliente, hay que moverla a ambito cliente.
7. **§5.1 dice usar el campo DIAS_VENCIMIENTO del ERP** y calcular solo si no
   tiene dato. El motor siempre calcula, porque §13 exige que cambiar la fecha
   de corte recalcule la clasificacion, y un campo precalculado solo vale para
   su propio corte. La reconciliacion demuestra que ambos coinciden en las 120
   filas. Falta decidir si se guarda `origen_dias` para dejarlo explicito.
8. **¿"Vence hoy" debe seguir contando como vencida en la exportacion?**
   Medido sobre el archivo: el ERP suma los saldos de dias=0 dentro de su
   columna "vencido menor o igual a 30". Son 84.500.000 de 506.400.000, el
   16,7% de la cartera, hoy reportado como vencido sin estarlo. El motor los
   separa en B01 (C-14) y `COLUMNAS_ERP` guarda la equivalencia para poder
   reproducir las columnas del ERP en la exportacion de §9. Falta decidir cual
   de las dos lecturas se presenta como oficial en el panel.
9. **Sobre la aplicacion de creditos**, tres decisiones que la regla no cubria
   y que se tomaron de forma explicita:
   - **Cascada.** Si el credito supera la factura mas antigua, el remanente
     pasa a la siguiente. Descartarlo perderia dinero del cliente.
   - **"Mas antigua" se mide por fecha de vencimiento**, no de emision. En el
     archivo de prueba da igual porque todos los plazos son de 30 dias, pero
     con plazos distintos no. Confirmar cual es el criterio de Busint.
   - **Una factura que el credito deja en cero no genera alerta** y no cuenta
     para R03. Cobrar cero es ruido. Queda registrada en
     `facturas_saldadas_por_credito`.
   - Si el credito cubre toda la cartera del cliente, el sobrante se reporta en
     `creditos_a_favor`, porque ese cliente ya no aparece en la lista de
     trabajo y su saldo a favor se perderia.
10. **Contrato del API del ERP.** `FuenteAPI` asume una respuesta con la lista
   en `datos` y la pagina siguiente en `siguiente`. Ambos son parametrizables,
   pero hay que confirmarlos contra el API real, junto con el metodo de
   autenticacion (hoy Bearer) y si acepta la fecha de corte como parametro.

## D. Origenes de datos

Implementados: Excel, CSV y API REST, todos detras del mismo contrato
`FuenteDatos`. Falta:

- **Lectura SQL directa** sobre el MySQL de Busint (escenario A de §4.3). Es
  fase 2 porque necesita SQLAlchemy y el esquema real de las tablas.
- El `MapeoCampos` de la lectura SQL, que sera distinto al del archivo plano.

## E. Nota tecnica

El documento fija Python 3.12. El proyecto declara `>=3.11` porque es lo
disponible en el entorno actual; el codigo no usa nada exclusivo de 3.12.
