/**
 * Cartera de ejemplo con la que arranca el banco de pruebas.
 *
 * Esta elegida para que, moviendo la fecha de corte, dispare el catalogo
 * completo A01-A12 y los marcadores M04 y M05. Incluye ademas los dos casos que
 * no generan alerta y conviene ver funcionando:
 *
 *   F-109  trae una nota credito sin aplicar, que se netea contra la factura
 *          mas antigua del cliente y no contra la suya (C-10).
 *   F-110  tiene saldo negativo: es credito a favor y nunca es mora
 *          (§5.3, caso T09).
 */
export const CLIENTES = {
  "900111": "DISTRIBUIDORA DEL NORTE SAS",
  "900222": "AGROINDUSTRIA DEL VALLE SAS",
};

export const CARTERA = [
  ["F-101", "900111", "2026-09-20", "4200000", "0"],
  ["F-102", "900111", "2026-09-05", "2800000", "0"],
  ["F-103", "900111", "2026-08-21", "9500000", "0"],
  ["F-104", "900111", "2026-08-06", "1750000", "0"],
  ["F-105", "900111", "2026-07-07", "12400000", "0"],
  ["F-106", "900111", "2026-06-02", "5800000", "0"],
  ["F-107", "900111", "2026-04-03", "3200000", "0"],
  ["F-108", "900111", "2026-02-02", "8600000", "0"],
  ["F-109", "900111", "2026-09-12", "3000000", "2500000"],
  ["F-110", "900111", "2026-03-01", "-900000", "0"],
  ["F-201", "900222", "2026-08-14", "26500000", "0"],
  ["F-202", "900222", "2026-07-20", "1200000", "0"],
  ["F-203", "900222", "2026-05-15", "4800000", "0"],
].map(([factura, cliente, vencimiento, saldo, credito]) => ({
  factura, cliente, vencimiento, saldo, credito,
  nombre: CLIENTES[cliente],
  // El plazo de credito no lo usa ninguna regla; solo desempata la antiguedad
  // cuando dos facturas vencen el mismo dia.
  emision: new Date(Date.parse(vencimiento + "T00:00:00Z") - 30 * 86400000)
    .toISOString().slice(0, 10),
}));

/** Umbrales de arranque: los mismos con que corre hoy el sistema. */
export const UMBRALES = {
  dias_preventivos: "15",
  n_facturas_vencidas: "3",
  pct_mayor_90_umbral: "40",
  umbral_saldo_alto: "",
  umbral_saldo_critico: "",
  dias_sin_gestion: "",
};

export const CORTE_INICIAL = "2026-08-21";
export const GESTION_DESDE = "2026-06-01";
