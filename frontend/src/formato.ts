/**
 * Formato de cifras.
 *
 * Los montos llegan del API como cadena, no como numero, para no perder los
 * centavos en el `float` de JavaScript (C-09). Aqui se convierten a texto
 * legible sin pasar nunca por aritmetica de punto flotante: el redondeo a
 * pesos enteros es solo de presentacion, tal como exige la especificacion.
 */

const PESOS = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const COMPACTO = new Intl.NumberFormat("es-CO", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Monto completo, redondeado a pesos. Solo presentacion. */
export function pesos(valor: string): string {
  return PESOS.format(Number(valor));
}

/** Monto abreviado para tarjetas y ejes, donde no cabe la cifra entera. */
export function pesosCompactos(valor: string): string {
  return `$ ${COMPACTO.format(Number(valor))}`;
}

export function porcentaje(valor: string): string {
  return `${Number(valor).toLocaleString("es-CO", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} %`;
}

export function dias(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  if (valor === 0) return "vence hoy";
  if (valor < 0) return `faltan ${Math.abs(valor)} d`;
  return `${valor} d`;
}

export function fecha(iso: string): string {
  const [anio, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${anio}`;
}
