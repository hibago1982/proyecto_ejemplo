/**
 * Explicacion de la alerta (§7.4).
 *
 * "Al posar el cursor sobre una severidad, el sistema explica la cadena:
 * bucket asignado, regla que elevo la prioridad, parametro vigente y valor que
 * la disparo."
 *
 * El texto no se compone aqui: llega hecho del motor, que es quien conoce la
 * regla. Componerlo en el navegador seria reimplementar la regla en el sitio
 * donde nadie la prueba.
 *
 * Se muestra al pasar el cursor y tambien al enfocar con el teclado, porque
 * §16 exige que la pantalla sea operable sin raton.
 */
import { useState } from "react";

export function Explicacion({ texto }: { texto: string | null | undefined }) {
  // Dos estados y no uno: con uno solo, pasar el cursor la abria y el clic
  // siguiente la cerraba de inmediato, que es lo contrario de lo que espera
  // quien hace clic para leerla con calma.
  const [sobre, setSobre] = useState(false);
  const [fijado, setFijado] = useState(false);
  const visible = sobre || fijado;
  if (!texto) return null;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Por qué se disparó esta alerta"
        className="flex h-4 w-4 items-center justify-center rounded-full border border-filete text-micro font-semibold text-tenue transition-colors duration-estado hover:border-apagado hover:text-apagado"
        aria-expanded={visible}
        onMouseEnter={() => setSobre(true)}
        onMouseLeave={() => setSobre(false)}
        onFocus={() => setSobre(true)}
        onBlur={() => setSobre(false)}
        onClick={(e) => {
          // La fila entera navega al cliente: el clic en la explicacion no debe
          // arrastrar al usuario fuera de la lista.
          e.stopPropagation();
          setFijado((f) => !f);
        }}
      >
        ?
      </button>
      {visible && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-10 mb-1 w-64 -translate-x-1/2 rounded-lg border border-filete bg-white p-2 text-menor font-normal leading-relaxed text-tinta shadow-sm"
        >
          {texto}
        </span>
      )}
    </span>
  );
}
