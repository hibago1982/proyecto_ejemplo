/**
 * Motor de alertas de cartera — port a JavaScript del motor Python.
 *
 * ADVERTENCIA IMPORTANTE
 * ----------------------
 * Esto es una SEGUNDA implementacion de las reglas, y §16 exige una sola fuente
 * de calculo. Existe por una restriccion concreta: el banco de pruebas corre en
 * una pagina publicada cuya politica de seguridad bloquea las peticiones que
 * Pyodide necesita para traerse su WASM, asi que no se puede ejecutar el Python
 * real dentro del navegador.
 *
 * Lo que hace que esta copia no mienta: `tests/test_paridad_js.py` genera
 * escenarios aleatorios, los evalua con el motor Python y con este, y compara
 * alerta por alerta y cifra por cifra. Si los dos divergen, la suite falla.
 *
 * En produccion manda el motor Python. Esto es un banco de pruebas.
 *
 * Sobre el dinero: todo se maneja en centavos enteros. Un `Number` de
 * JavaScript no representa 1234567.89 sin error, y C-09 exige conservar los dos
 * decimales en el calculo. Los enteros hasta 2^53 cubren cifras muy por encima
 * de cualquier cartera real.
 */

// --------------------------------------------------------------------------
// Dinero y aritmetica exacta
// --------------------------------------------------------------------------

/** Convierte "1234567.89" a 123456789 centavos, sin pasar por punto flotante. */
export function aCentavos(valor) {
  const texto = String(valor).trim();
  const negativo = texto.startsWith("-");
  const [entera, decimal = ""] = texto.replace(/^[-+]/, "").split(".");
  const centavos =
    BigInt(entera || "0") * 100n + BigInt((decimal + "00").slice(0, 2));
  return Number(negativo ? -centavos : centavos);
}

export const deCentavos = (c) => (c / 100).toFixed(2);

/**
 * Redondeo al alza en la mitad, con aritmetica entera.
 *
 * `Math.round(x + 0.5)` sobre un cociente en punto flotante da resultados
 * distintos a los de Decimal justo en los empates, que es donde se nota.
 */
function mitadArriba(numerador, denominador) {
  if (denominador === 0) return 0;
  const signo = numerador < 0 !== denominador < 0 ? -1 : 1;
  const n = Math.abs(numerador);
  const d = Math.abs(denominador);
  const entero = Math.floor(n / d);
  const resto = n - entero * d;
  return signo * (2 * resto >= d ? entero + 1 : entero);
}

/** Porcentaje con dos decimales, expresado en centesimas de punto. */
export function porcentaje(parte, total) {
  if (total === 0) return 0;
  return mitadArriba(parte * 10000, total);
}

export const dePorcentaje = (p) => (p / 100).toFixed(2);

// --------------------------------------------------------------------------
// Vocabulario
// --------------------------------------------------------------------------

export const PRIORIDADES = ["Informativa", "Media", "Alta", "Muy alta", "Critica"];
const CRITICA = 4;

const elevar = (nivel, niveles) => Math.min(nivel + niveles, CRITICA);

/** Buckets de §5.2. Los limites son inclusivos en ambos extremos. */
export const BUCKETS = [
  { codigo: "B00", etiqueta: "Por vencer", desde: null, hasta: -1, color: "#2F6B9A", prioridad: 0, accion: "Seguimiento preventivo", alerta: null },
  { codigo: "B01", etiqueta: "Vence hoy", desde: 0, hasta: 0, color: "#B8860B", prioridad: 2, accion: "Gestionar hoy", alerta: "A02" },
  { codigo: "B02", etiqueta: "1-30 días", desde: 1, hasta: 30, color: "#B8860B", prioridad: 1, accion: "Recordatorio/cobro", alerta: "A03" },
  { codigo: "B03", etiqueta: "31-60 días", desde: 31, hasta: 60, color: "#E67E22", prioridad: 2, accion: "Cobranza", alerta: "A04" },
  { codigo: "B04", etiqueta: "61-90 días", desde: 61, hasta: 90, color: "#D32F2F", prioridad: 2, accion: "Cobranza prioritaria", alerta: "A05" },
  { codigo: "B05", etiqueta: "91-120 días", desde: 91, hasta: 120, color: "#9B1C1C", prioridad: 3, accion: "Escalar", alerta: "A06" },
  { codigo: "B06", etiqueta: "121-150 días", desde: 121, hasta: 150, color: "#9B1C1C", prioridad: 3, accion: "Escalar", alerta: "A07" },
  { codigo: "B07", etiqueta: "Más de 150 días", desde: 151, hasta: null, color: "#641220", prioridad: 4, accion: "Recuperación/comité", alerta: "A08" },
];

export const ETIQUETAS_ALERTA = {
  A01: "Próximo vencimiento", A02: "Vence hoy", A03: "Mora 1-30",
  A04: "Mora 31-60", A05: "Mora 61-90", A06: "Mora 91-120",
  A07: "Mora 121-150", A08: "Mora mayor a 150", A09: "Alta exposición",
  A10: "Cliente reincidente", A11: "Envejecimiento crítico", A12: "Sin gestión",
};

export const ETIQUETAS_MARCADOR = {
  M04: "Riesgo de envejecimiento", M05: "Riesgo crítico",
};

/** Catalogo de §5.4, con los parametros que cada regla necesita. */
export const REGLAS = [
  { codigo: "R01", etiqueta: "Saldo alto en mora", ambito: "factura", parametros: ["umbral_saldo_alto"], efecto: "eleva la prioridad un nivel" },
  { codigo: "R02", etiqueta: "Alta exposición", ambito: "factura", parametros: ["umbral_saldo_critico"], efecto: "emite A09" },
  { codigo: "R03", etiqueta: "Cliente reincidente", ambito: "cliente", parametros: ["n_facturas_vencidas"], efecto: "emite A10" },
  { codigo: "R04", etiqueta: "Riesgo de envejecimiento", ambito: "cliente", parametros: [], efecto: "marca M04 · más de 90 días" },
  { codigo: "R05", etiqueta: "Riesgo crítico", ambito: "cliente", parametros: [], efecto: "marca M05 · más de 150 días" },
  { codigo: "R06", etiqueta: "Próximo vencimiento", ambito: "factura", parametros: ["dias_preventivos"], efecto: "emite A01" },
  { codigo: "A11", etiqueta: "Envejecimiento crítico", ambito: "cliente", parametros: ["pct_mayor_90_umbral"], efecto: "emite A11" },
  { codigo: "A12", etiqueta: "Sin gestión", ambito: "factura", parametros: ["dias_sin_gestion"], efecto: "emite A12" },
];

const DIA = 86400000;
export const dias = (desde, hasta) =>
  Math.round((Date.parse(hasta + "T00:00:00Z") - Date.parse(desde + "T00:00:00Z")) / DIA);

const bucketDe = (d) =>
  BUCKETS.find((b) => (b.desde === null || d >= b.desde) && (b.hasta === null || d <= b.hasta));

// --------------------------------------------------------------------------
// Creditos (C-10)
// --------------------------------------------------------------------------

/**
 * Aplica las notas credito de cada cliente a su factura mas antigua, en cascada.
 *
 * El credito pertenece al cliente, no a la fila en que viaja. Si supera a la
 * mas antigua, el remanente pasa a la siguiente. Lo que sobra queda a favor y
 * nunca produce un saldo negativo.
 */
export function aplicarCreditos(movimientos) {
  const porCliente = new Map();
  for (const m of movimientos) {
    if (!porCliente.has(m.cliente)) porCliente.set(m.cliente, []);
    porCliente.get(m.cliente).push(m);
  }

  const netos = [];
  const rastros = [];

  for (const nit of [...porCliente.keys()].sort()) {
    const facturas = porCliente.get(nit);
    const credito = facturas.reduce((s, m) => s + aCentavos(m.credito ?? "0"), 0);

    if (credito <= 0) {
      netos.push(...facturas.map((m) => ({ ...m, saldoC: aCentavos(m.saldo), brutoC: aCentavos(m.saldo), aplicadoC: 0 })));
      continue;
    }

    // De la mas antigua a la mas reciente, por vencimiento. El numero de
    // factura desempata para que el reparto no dependa del orden de llegada.
    const ordenadas = [...facturas].sort((a, b) =>
      a.vencimiento.localeCompare(b.vencimiento) ||
      a.emision.localeCompare(b.emision) ||
      a.factura.localeCompare(b.factura));

    let restante = credito;
    const aplicaciones = [];
    for (const m of ordenadas) {
      const bruto = aCentavos(m.saldo);
      const aplicado = bruto > 0 ? Math.min(restante, bruto) : 0;
      if (aplicado > 0) {
        aplicaciones.push([m.factura, aplicado]);
        restante -= aplicado;
      }
      netos.push({ ...m, saldoC: bruto - aplicado, brutoC: bruto, aplicadoC: aplicado });
    }
    rastros.push({ cliente: nit, creditoTotal: credito, aplicaciones, noAplicado: restante });
  }

  return { netos, rastros };
}

// --------------------------------------------------------------------------
// Evaluacion
// --------------------------------------------------------------------------

const definido = (p, n) => p[n] !== undefined && p[n] !== null && p[n] !== "";

/** Motivo por el que una regla no se evalua, o null si procede. */
export function motivoInactiva(regla, parametros) {
  const faltan = regla.parametros.filter((n) => !definido(parametros, n));
  if (faltan.length === 0) return null;
  return `La empresa no ha asignado valor a: ${faltan.join(", ")}. La regla permanece inactiva (C-05).`;
}

/**
 * Evalua un corte completo.
 *
 * El orden es el del motor Python y no es casual: los creditos van primero
 * porque cambian el saldo, y el saldo alimenta tanto el aging como los umbrales
 * monetarios. Las reglas de cliente van al final porque necesitan agregados que
 * solo existen tras recorrer todas las facturas.
 */
export function evaluar({ corte, movimientos, parametros, gestiones = {} }) {
  const p = parametros;
  const reglasInactivas = {};
  for (const r of REGLAS) {
    const motivo = motivoInactiva(r, p);
    if (motivo) reglasInactivas[r.codigo] = motivo;
  }
  const activa = (codigo) => !(codigo in reglasInactivas);

  const { netos, rastros } = aplicarCreditos(movimientos);
  const deudores = netos.filter((m) => m.saldoC > 0);
  const noDeudores = netos.filter((m) => m.saldoC <= 0);

  const alertas = [];
  const marcadores = [];
  const perfiles = new Map();
  const facturas = [];
  const porBucket = {};
  const facturasPorBucket = {};

  for (const m of netos) {
    const d = dias(m.vencimiento, corte);
    const b = m.saldoC > 0 ? bucketDe(d) : null;
    facturas.push({
      factura: m.factura, cliente: m.cliente, dias: d,
      bucket: b?.codigo ?? null,
      sinBucket: b ? null : (m.saldoC < 0 ? "Crédito a favor" : "Saldada por crédito"),
      saldoC: m.saldoC, brutoC: m.brutoC, aplicadoC: m.aplicadoC,
      alertas: [],
    });
  }

  for (const m of deudores) {
    const d = dias(m.vencimiento, corte);
    const b = bucketDe(d);
    const fila = facturas.find((f) => f.factura === m.factura);

    if (!perfiles.has(m.cliente)) {
      perfiles.set(m.cliente, {
        nit: m.cliente, nombre: m.nombre ?? m.cliente,
        porVencer: 0, venceHoy: 0, vencida: 0, mayor90: 0, mayor150: 0,
        diasMax: 0, nFacturas: 0, nVencidas: 0, prioridad: 0, marcadores: [],
      });
    }
    const perfil = perfiles.get(m.cliente);
    perfil.nFacturas += 1;
    if (b.hasta !== null && b.hasta < 0) perfil.porVencer += m.saldoC;
    else if (b.desde === 0 && b.hasta === 0) perfil.venceHoy += m.saldoC;
    else { perfil.vencida += m.saldoC; perfil.nVencidas += 1; }
    if (d > 90) perfil.mayor90 += m.saldoC;
    if (d > 150) perfil.mayor150 += m.saldoC;
    perfil.diasMax = Math.max(perfil.diasMax, d);

    porBucket[b.codigo] = (porBucket[b.codigo] ?? 0) + m.saldoC;
    facturasPorBucket[b.codigo] = (facturasPorBucket[b.codigo] ?? 0) + 1;

    // --- Reglas de ambito factura ---
    const disparadas = [];

    if (activa("R01") && m.saldoC > aCentavos(p.umbral_saldo_alto) && d > 30) {
      disparadas.push({
        regla: "R01", eleva: 1,
        explicacion: `R01: saldo de ${deCentavos(m.saldoC)} con ${d} dias vencida (${deCentavos(m.saldoC)} contra umbral_saldo_alto=${p.umbral_saldo_alto})`,
      });
    }
    if (activa("R02") && m.saldoC > aCentavos(p.umbral_saldo_critico)) {
      disparadas.push({
        regla: "R02", alerta: "A09", prioridad: 2, accion: "Revisar exposicion",
        explicacion: `R02: saldo de ${deCentavos(m.saldoC)} sobre el umbral critico (${deCentavos(m.saldoC)} contra umbral_saldo_critico=${p.umbral_saldo_critico})`,
      });
    }
    if (activa("R06")) {
      const prev = Number(p.dias_preventivos);
      if (d >= -prev && d < 0) {
        disparadas.push({
          regla: "R06", alerta: "A01", prioridad: 1, accion: "Registrar seguimiento",
          explicacion: `R06: la factura vence en ${-d} dias (${-d} contra dias_preventivos=${prev})`,
        });
      }
    }
    if (activa("A12")) {
      const desde = gestiones[`${m.cliente}|${m.factura}`] ?? gestiones[`${m.cliente}|*`];
      if (desde) {
        const sinGestion = dias(desde, corte);
        const umbral = Number(p.dias_sin_gestion);
        if (sinGestion >= umbral) {
          disparadas.push({
            regla: "A12", alerta: "A12", prioridad: 2, accion: "Escalar al responsable",
            explicacion: `A12: lleva ${sinGestion} dias sin gestion registrada (${sinGestion} contra dias_sin_gestion=${umbral})`,
          });
        }
      }
    }

    const elevaciones = disparadas.reduce((s, x) => s + (x.eleva ?? 0), 0);
    let prioridad = elevaciones ? elevar(b.prioridad, elevaciones) : b.prioridad;

    if (b.alerta) {
      alertas.push({
        codigo: b.alerta, etiqueta: ETIQUETAS_ALERTA[b.alerta], prioridad,
        prioridadBase: PRIORIDADES[b.prioridad], accion: b.accion,
        cliente: m.cliente, factura: m.factura, bucket: b.codigo, dias: d,
        saldoC: m.saldoC,
        explicacion: `${b.codigo}: la factura esta en el rango ${b.etiqueta}`,
        elevadaPor: disparadas.filter((x) => x.eleva).map((x) => x.explicacion),
      });
      fila.alertas.push(b.alerta);
    }

    for (const x of disparadas) {
      if (!x.alerta) continue;
      alertas.push({
        codigo: x.alerta, etiqueta: ETIQUETAS_ALERTA[x.alerta], prioridad: x.prioridad,
        accion: x.accion, cliente: m.cliente, factura: m.factura,
        bucket: b.codigo, dias: d, saldoC: m.saldoC,
        explicacion: x.explicacion, elevadaPor: [],
      });
      fila.alertas.push(x.alerta);
      prioridad = Math.max(prioridad, x.prioridad);
    }

    perfil.prioridad = Math.max(perfil.prioridad, prioridad);
    fila.alertas.sort();
  }

  // --- Reglas de ambito cliente, sobre el perfil ya completo ---
  for (const perfil of perfiles.values()) {
    const total = perfil.porVencer + perfil.venceHoy + perfil.vencida;
    const pct90 = porcentaje(perfil.mayor90, total);

    if (activa("R03")) {
      const n = Number(p.n_facturas_vencidas);
      if (perfil.nVencidas >= n) {
        alertas.push({
          codigo: "A10", etiqueta: ETIQUETAS_ALERTA.A10, prioridad: 2,
          accion: "Revisar comportamiento", cliente: perfil.nit, factura: null,
          bucket: null, dias: null, saldoC: null, elevadaPor: [],
          explicacion: `R03: el cliente tiene ${perfil.nVencidas} facturas vencidas (${perfil.nVencidas} contra n_facturas_vencidas=${n})`,
        });
        perfil.prioridad = Math.max(perfil.prioridad, 2);
      }
    }
    if (perfil.diasMax > 90) {
      marcadores.push({
        codigo: "M04", etiqueta: ETIQUETAS_MARCADOR.M04, cliente: perfil.nit,
        explicacion: `R04: su factura mas antigua lleva ${perfil.diasMax} dias vencida`,
      });
      perfil.marcadores.push("M04");
      perfil.prioridad = Math.max(perfil.prioridad, 3);
    }
    if (perfil.diasMax > 150) {
      marcadores.push({
        codigo: "M05", etiqueta: ETIQUETAS_MARCADOR.M05, cliente: perfil.nit,
        explicacion: `R05: su factura mas antigua lleva ${perfil.diasMax} dias vencida`,
      });
      perfil.marcadores.push("M05");
      perfil.prioridad = Math.max(perfil.prioridad, 4);
    }
    if (activa("A11")) {
      const umbral = Math.round(Number(p.pct_mayor_90_umbral) * 100);
      if (pct90 > umbral) {
        alertas.push({
          codigo: "A11", etiqueta: ETIQUETAS_ALERTA.A11, prioridad: 3,
          accion: "Intervencion", cliente: perfil.nit, factura: null,
          bucket: null, dias: null, saldoC: null, elevadaPor: [],
          explicacion: `A11: el ${dePorcentaje(pct90)}% de su cartera supera los 90 dias (${dePorcentaje(pct90)} contra pct_mayor_90_umbral=${p.pct_mayor_90_umbral})`,
        });
        perfil.prioridad = Math.max(perfil.prioridad, 3);
      }
    }
  }

  const g = [...perfiles.values()].reduce(
    (a, c) => ({
      porVencer: a.porVencer + c.porVencer, venceHoy: a.venceHoy + c.venceHoy,
      vencida: a.vencida + c.vencida, mayor90: a.mayor90 + c.mayor90,
      mayor150: a.mayor150 + c.mayor150, nFacturas: a.nFacturas + c.nFacturas,
    }),
    { porVencer: 0, venceHoy: 0, vencida: 0, mayor90: 0, mayor150: 0, nFacturas: 0 },
  );
  const total = g.porVencer + g.venceHoy + g.vencida;

  return {
    corte,
    globales: {
      carteraTotal: total, ...g, nClientes: perfiles.size,
      pctVencida: porcentaje(g.vencida, total),
      pct90: porcentaje(g.mayor90, total),
    },
    porBucket, facturasPorBucket,
    facturas: facturas.sort((a, b) => b.dias - a.dias),
    alertas: alertas.sort((a, b) => b.prioridad - a.prioridad || a.codigo.localeCompare(b.codigo)),
    marcadores,
    clientes: [...perfiles.values()].map((c) => {
      const t = c.porVencer + c.venceHoy + c.vencida;
      return { ...c, carteraTotal: t, pctVencida: porcentaje(c.vencida, t), pct90: porcentaje(c.mayor90, t) };
    }).sort((a, b) => b.prioridad - a.prioridad || b.vencida - a.vencida),
    noDeudores: noDeudores.map((m) => ({ factura: m.factura, cliente: m.cliente, saldoC: m.saldoC })),
    creditos: rastros,
    reglasInactivas,
  };
}
