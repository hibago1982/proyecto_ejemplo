/**
 * Color de severidad (§7.2).
 *
 * "Chip con tinte del propio color al 9 %, borde al 17 % y texto en color
 * pleno. Senala sin gritar." Los valores salen de la especificacion, no de una
 * eleccion estetica.
 *
 * §16 y §7.1: el color nunca es la unica senal. Cada chip lleva siempre su
 * etiqueta textual, de modo que la pantalla siga siendo legible sin ver color.
 */

export const PRIORIDADES = [
  "Informativa",
  "Media",
  "Alta",
  "Muy alta",
  "Critica",
] as const;

/** Color pleno por nivel, alineado con la paleta de aging de §5.2. */
const TINTA: Record<number, string> = {
  0: "#2F6B9A",
  1: "#B8860B",
  2: "#E67E22",
  3: "#9B1C1C",
  4: "#641220",
};

export function colorDePrioridad(nivel: number): string {
  return TINTA[nivel] ?? TINTA[0]!;
}

/** Estilos del chip: tinte al 9 %, borde al 17 %, texto pleno. */
export function chipDeSeveridad(nivel: number): React.CSSProperties {
  const color = colorDePrioridad(nivel);
  return {
    color,
    backgroundColor: `${color}17`, // 9 % en hexadecimal
    borderColor: `${color}2B`, // 17 %
  };
}

export function etiquetaDePrioridad(nivel: number): string {
  return PRIORIDADES[nivel] ?? "Informativa";
}
