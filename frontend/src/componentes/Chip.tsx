/**
 * Chip de severidad.
 *
 * §16: el color nunca es la unica senal. El chip siempre lleva texto, y para
 * lectores de pantalla ademas un `title` que nombra el nivel.
 */
import { chipDeSeveridad, etiquetaDePrioridad } from "../severidad";

export function Chip({ nivel, texto }: { nivel: number; texto?: string }) {
  const etiqueta = texto ?? etiquetaDePrioridad(nivel);
  return (
    <span
      className="inline-flex items-center rounded-full border px-2 py-0.5 text-micro font-semibold"
      style={chipDeSeveridad(nivel)}
      title={`Prioridad ${etiquetaDePrioridad(nivel)}`}
    >
      {etiqueta}
    </span>
  );
}
