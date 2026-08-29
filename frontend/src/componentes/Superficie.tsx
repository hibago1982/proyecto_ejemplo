/**
 * Superficie base de §7.2: blanco puro, filete de 1 px, radio de 16, sin sombra.
 *
 * Existe como componente y no como clase suelta para que el minimalismo no se
 * erosione tarjeta a tarjeta: quien anada una pantalla nueva hereda la misma
 * superficie sin tener que recordar los valores.
 */
import type { ReactNode } from "react";

export function Superficie({
  children,
  titulo,
  accion,
  className = "",
}: {
  children: ReactNode;
  titulo?: string;
  accion?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-tarjeta border border-filete bg-white p-dentro ${className}`}
    >
      {(titulo || accion) && (
        <header className="mb-entre flex items-baseline justify-between">
          {titulo && (
            <h2 className="text-menor font-semibold uppercase tracking-wide text-apagado">
              {titulo}
            </h2>
          )}
          {accion}
        </header>
      )}
      {children}
    </section>
  );
}
