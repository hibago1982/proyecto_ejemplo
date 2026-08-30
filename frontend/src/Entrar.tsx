/**
 * Inicio de sesion (§8.4).
 *
 * El mensaje de error es el que devuelve el servidor, que no distingue entre
 * usuario inexistente y clave incorrecta: distinguirlos permitiria averiguar
 * que usuarios existen.
 */
import { useState } from "react";

import type { Cliente, Sesion } from "./api/cliente";
import { Superficie } from "./componentes/Superficie";

export function Entrar({
  cliente,
  onEntrar,
}: {
  cliente: Cliente;
  onEntrar: (sesion: Sesion) => void;
}) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      onEntrar(await cliente.entrar(usuario, clave));
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No se pudo entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm p-marco pt-[12vh]">
      <p className="mb-2 text-menor font-semibold uppercase tracking-widest text-[#2F6B9A]">
        Busint
      </p>
      <h1 className="mb-entre text-titulo font-semibold tracking-tight text-tinta">
        Cartera
      </h1>
      <Superficie>
        <form onSubmit={enviar} className="space-y-entre">
          <label className="block text-menor text-apagado">
            Usuario
            <input
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              autoComplete="username"
              autoFocus
              className="mt-1 w-full rounded-lg border border-filete px-2 py-1.5 text-base text-tinta focus:border-[#2F6B9A] focus:outline-none"
            />
          </label>
          <label className="block text-menor text-apagado">
            Clave
            <input
              type="password"
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              autoComplete="current-password"
              className="mt-1 w-full rounded-lg border border-filete px-2 py-1.5 text-base text-tinta focus:border-[#2F6B9A] focus:outline-none"
            />
          </label>
          {error && <p className="text-menor text-[#9B1C1C]">{error}</p>}
          <button
            type="submit"
            disabled={enviando || !usuario || !clave}
            className="w-full rounded-lg bg-[#2F6B9A] px-3 py-1.5 text-base font-medium text-white transition-colors duration-estado disabled:opacity-40"
          >
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </Superficie>
    </div>
  );
}
