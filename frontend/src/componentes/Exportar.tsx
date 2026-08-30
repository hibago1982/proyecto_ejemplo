/**
 * Botones de exportacion (§9).
 *
 * Descargan con fetch autenticado en vez de con un enlace: `<a href>` no lleva
 * cabeceras y el servidor devolveria 401. El PDF de un corte grande tarda
 * varios segundos en generarse, asi que el boton avisa mientras tanto en vez
 * de parecer que no hizo nada.
 */
import { useState } from "react";

import type { Cliente } from "../api/cliente";

type Formato = "excel" | "pdf";

export function Exportar({ cliente, corte }: { cliente: Cliente; corte?: string }) {
  const [generando, setGenerando] = useState<Formato | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function descargar(formato: Formato) {
    setGenerando(formato);
    setError(null);
    try {
      const { blob, nombre } = await cliente.descargar(formato, corte);
      const url = URL.createObjectURL(blob);
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download = nombre;
      enlace.click();
      // Sin revocar, cada descarga deja el archivo entero retenido en memoria.
      URL.revokeObjectURL(url);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo exportar.");
    } finally {
      setGenerando(null);
    }
  }

  return (
    <span className="flex items-center gap-entre">
      {(["excel", "pdf"] as const).map((formato) => (
        <button
          key={formato}
          type="button"
          onClick={() => descargar(formato)}
          disabled={generando !== null}
          className="transition-colors duration-estado hover:text-tinta disabled:opacity-40"
        >
          {generando === formato
            ? "Generando…"
            : formato === "excel"
              ? "Excel"
              : "PDF"}
        </button>
      ))}
      {error && <span className="text-[#9B1C1C]">{error}</span>}
    </span>
  );
}
