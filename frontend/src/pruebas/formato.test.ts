/**
 * C-09 de extremo a extremo: los montos llegan como cadena y no deben pasar
 * por aritmetica de punto flotante antes de mostrarse.
 */
import { describe, expect, it } from "vitest";

import { dias, pesos, porcentaje } from "../formato";
import { chipDeSeveridad, etiquetaDePrioridad } from "../severidad";

/**
 * Intl separa el simbolo de la cifra con un espacio duro (U+00A0), no con uno
 * normal. Es lo correcto tipograficamente: evita que el "$" quede colgando al
 * final de una linea. Se nombra aqui para que las comparaciones sean
 * explicitas y no dos cadenas que parecen iguales y no lo son.
 */
const DURO = "\u00A0";

describe("formato de montos", () => {
  it("redondea a pesos solo en presentacion", () => {
    expect(pesos("1234567.89")).toBe(`$${DURO}1.234.568`);
  });

  it("conserva la magnitud de cifras grandes", () => {
    expect(pesos("506400000.00")).toBe(`$${DURO}506.400.000`);
  });

  it("formatea porcentajes con un decimal", () => {
    expect(porcentaje("16.69")).toBe("16,7 %");
  });

  it("no arrastra el error binario de los flotantes", () => {
    // El monto llega como cadena justamente para que este caso no se estropee.
    expect(pesos("0.10")).toBe(`$${DURO}0`);
    expect(pesos("999999999.99")).toBe(`$${DURO}1.000.000.000`);
  });
});

describe("dias de vencimiento", () => {
  it("distingue vence hoy de vencida y por vencer", () => {
    expect(dias(0)).toBe("vence hoy");
    expect(dias(-10)).toBe("faltan 10 d");
    expect(dias(45)).toBe("45 d");
  });

  it("no inventa un cero cuando no hay dato", () => {
    expect(dias(null)).toBe("—");
  });
});

describe("severidad", () => {
  it("usa los cinco niveles de la especificacion", () => {
    expect(etiquetaDePrioridad(3)).toBe("Muy alta");
    expect(etiquetaDePrioridad(4)).toBe("Critica");
  });

  it("tinta el chip al 9 % y el borde al 17 %", () => {
    const estilo = chipDeSeveridad(4);
    expect(estilo.color).toBe("#641220");
    expect(estilo.backgroundColor).toBe("#64122017");
    expect(estilo.borderColor).toBe("#6412202B");
  });
});
