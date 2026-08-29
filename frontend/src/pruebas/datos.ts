/** Respuestas de ejemplo, con las cifras reales del archivo de prueba. */
import type { Corte, DetalleCliente, FilaGestion, ListaGestion, Panel } from "../api/cliente";

export const PANEL: Panel = {
  empresa_id: "E01",
  corte: "2026-08-21",
  generado: "2026-08-21T06:00:00",
  version_parametros: "a1b2c3",
  n_clientes: 30,
  n_facturas: 120,
  reglas_inactivas: {
    R01: "La empresa no ha asignado valor a: umbral_saldo_alto.",
  },
  kpis: [
    { codigo: "cartera_total", etiqueta: "Cartera total", valor: "506400000.00", pct_sobre_total: "100.00" },
    { codigo: "por_vencer", etiqueta: "Por vencer", valor: "91600000.00", pct_sobre_total: "18.09" },
    { codigo: "vence_hoy", etiqueta: "Vence hoy", valor: "84500000.00", pct_sobre_total: "16.69" },
    { codigo: "vencida", etiqueta: "Vencida", valor: "330300000.00", pct_sobre_total: "65.23" },
    { codigo: "mayor_90", etiqueta: "Mas de 90 dias", valor: "74650000.00", pct_sobre_total: "14.74" },
  ],
  aging: [
    { bucket: "B00", etiqueta: "Por vencer", color: "#2F6B9A", saldo: "91600000.00", facturas: 0, pct_sobre_total: "18.09" },
    { bucket: "B01", etiqueta: "Vence hoy", color: "#B8860B", saldo: "84500000.00", facturas: 20, pct_sobre_total: "16.69" },
    { bucket: "B02", etiqueta: "1-30 dias", color: "#B8860B", saldo: "70450000.00", facturas: 20, pct_sobre_total: "13.91" },
  ],
  ranking: [
    {
      cliente_nit: "90010001818",
      cliente_nombre: "TEXTILES DE ANTIOQUIA SAS",
      cartera_total: "38000000.00",
      vencida: "38000000.00",
      pct_vencida: "100.00",
      pct_90: "25.00",
      dias_max: 150,
      n_vencidas: 4,
      prioridad: 3,
      prioridad_etiqueta: "Muy alta",
      marcadores: ["M04"],
    },
  ],
};

export const CORTES: Corte[] = [
  {
    corte: "2026-08-21",
    generado: "2026-08-21T06:00:00",
    version_parametros: "a1b2c3",
    cartera_total: "506400000.00",
    n_clientes: 30,
  },
];

const FILA: FilaGestion = {
  id: 1,
  cliente_nit: "90010001818",
  cliente_nombre: "TEXTILES DE ANTIOQUIA SAS",
  factura: "3018",
  codigo: "A07",
  etiqueta: "Mora 121-150",
  bucket: "B06",
  dias: 150,
  saldo: "3200000.00",
  saldo_bruto: null,
  credito_aplicado: null,
  prioridad: 3,
  prioridad_etiqueta: "Muy alta",
  accion: "Escalar",
  estado: "activa",
  explicacion: "B06: la factura esta en el rango 121-150 dias",
  vendedor: "ANA MARIA RESTREPO",
  zona: "NACIONAL",
};

/** Factura con nota credito aplicada: la diferencia contra el ERP debe verse. */
const FILA_CON_CREDITO: FilaGestion = {
  ...FILA,
  id: 2,
  factura: "3048",
  codigo: "A04",
  etiqueta: "Mora 31-60",
  bucket: "B03",
  dias: 45,
  saldo: "600000.00",
  saldo_bruto: "1000000.00",
  credito_aplicado: "400000.00",
  prioridad: 2,
  prioridad_etiqueta: "Alta",
  accion: "Cobranza",
  explicacion: "B03: la factura esta en el rango 31-60 dias",
};

/** Alerta de cliente: no cuelga de ninguna factura (C-17). */
const FILA_DE_CLIENTE: FilaGestion = {
  ...FILA,
  id: 3,
  factura: "",
  codigo: "A10",
  etiqueta: "Cliente reincidente",
  bucket: null,
  dias: null,
  saldo: null,
  prioridad: 2,
  prioridad_etiqueta: "Alta",
  accion: "Revisar comportamiento",
  explicacion: "R03: el cliente tiene 4 facturas vencidas (4 contra n_facturas_vencidas=3)",
};

export const LISTA: ListaGestion = {
  corte: "2026-08-21",
  total: 3,
  pagina: 1,
  por_pagina: 40,
  filas: [FILA, FILA_CON_CREDITO, FILA_DE_CLIENTE],
};

export const DETALLE: DetalleCliente = {
  cliente_nit: "90010001818",
  cliente_nombre: "TEXTILES DE ANTIOQUIA SAS",
  corte: "2026-08-21",
  cartera_total: "38000000.00",
  por_vencer: "0.00",
  vence_hoy: "0.00",
  vencida: "38000000.00",
  pct_vencida: "100.00",
  mayor_90: "9500000.00",
  pct_90: "25.00",
  mayor_150: "0.00",
  dias_max: 150,
  n_facturas: 4,
  n_vencidas: 4,
  prioridad: 3,
  prioridad_etiqueta: "Muy alta",
  marcadores: ["M04"],
  alertas: [FILA, FILA_CON_CREDITO, FILA_DE_CLIENTE],
};
