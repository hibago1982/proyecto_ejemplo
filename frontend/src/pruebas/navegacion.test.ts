/**
 * Navegacion por hash.
 *
 * Cada vista tiene direccion propia porque un gestor tiene que poder pasarle a
 * su coordinador el enlace de un cliente, no explicarle como llegar.
 */
import { describe, expect, it } from "vitest";

import { leerVista, rutaDe } from "../navegacion";

describe("leer la vista desde el hash", () => {
  it("sin hash muestra el panel", () => {
    expect(leerVista("")).toEqual({ nombre: "panel" });
    expect(leerVista("#/")).toEqual({ nombre: "panel" });
  });

  it("reconoce la lista de gestion", () => {
    expect(leerVista("#/gestion")).toEqual({ nombre: "gestion" });
  });

  it("reconoce el detalle de un cliente", () => {
    expect(leerVista("#/clientes/90010001818")).toEqual({
      nombre: "cliente",
      nit: "90010001818",
    });
  });

  it("una ruta desconocida cae en el panel en vez de romperse", () => {
    expect(leerVista("#/inventado")).toEqual({ nombre: "panel" });
  });

  it("un cliente sin NIT no produce una vista rota", () => {
    expect(leerVista("#/clientes/")).toEqual({ nombre: "panel" });
  });
});

describe("construir la ruta", () => {
  it("es reversible", () => {
    const vistas = [
      { nombre: "panel" },
      { nombre: "gestion" },
      { nombre: "cliente", nit: "900123" },
    ] as const;
    for (const vista of vistas) {
      expect(leerVista(rutaDe(vista))).toEqual(vista);
    }
  });

  it("escapa los NIT con caracteres especiales", () => {
    const ruta = rutaDe({ nombre: "cliente", nit: "900/123 #4" });
    expect(ruta).not.toContain(" ");
    expect(leerVista(ruta)).toEqual({ nombre: "cliente", nit: "900/123 #4" });
  });
});
