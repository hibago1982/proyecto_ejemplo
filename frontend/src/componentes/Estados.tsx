/** Estados de carga, error y vacio, para que ninguna pantalla quede en blanco. */
import { Superficie } from "./Superficie";

export function Cargando({ que = "los datos" }: { que?: string }) {
  return (
    <Superficie>
      <p className="py-8 text-center text-base text-tenue">Cargando {que}…</p>
    </Superficie>
  );
}

export function Fallo({ error }: { error: unknown }) {
  // El backend devuelve detalles legibles y accionables ("revisa el ERP",
  // "ejecuta el motor antes de consultar"): se muestran tal cual en vez de
  // reemplazarlos por un mensaje generico.
  const mensaje =
    error instanceof Error ? error.message : "Ocurrió un error inesperado.";
  return (
    <Superficie>
      <p className="py-8 text-center text-base text-[#9B1C1C]">{mensaje}</p>
    </Superficie>
  );
}
