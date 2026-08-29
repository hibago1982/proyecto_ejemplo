/**
 * Navegacion por el hash de la URL.
 *
 * Sin dependencia de router: tres vistas no justifican una libreria. Lo que si
 * importa es que cada vista tenga direccion propia, porque §16 exige drill-down
 * de indicador a cliente y a factura, y porque un gestor tiene que poder pasarle
 * a su coordinador el enlace de un cliente concreto en vez de explicarle como
 * llegar.
 */
import { useEffect, useState } from "react";

export type Vista =
  | { nombre: "panel" }
  | { nombre: "gestion" }
  | { nombre: "cliente"; nit: string };

export function leerVista(hash: string = window.location.hash): Vista {
  const ruta = hash.replace(/^#\/?/, "");
  if (ruta.startsWith("clientes/")) {
    const nit = decodeURIComponent(ruta.slice("clientes/".length));
    if (nit) return { nombre: "cliente", nit };
  }
  if (ruta === "gestion") return { nombre: "gestion" };
  return { nombre: "panel" };
}

export function rutaDe(vista: Vista): string {
  switch (vista.nombre) {
    case "gestion":
      return "#/gestion";
    case "cliente":
      return `#/clientes/${encodeURIComponent(vista.nit)}`;
    default:
      return "#/";
  }
}

export function irA(vista: Vista): void {
  window.location.hash = rutaDe(vista);
}

export function useVista(): Vista {
  const [vista, setVista] = useState<Vista>(() => leerVista());

  useEffect(() => {
    const alCambiar = () => setVista(leerVista());
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  return vista;
}
