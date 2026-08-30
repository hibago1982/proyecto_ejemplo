/**
 * Registro de una gestion de cobranza (§11).
 *
 * El compromiso de pago es opcional, pero si se abre, van sus dos partes: media
 * promesa no se puede seguir, y el backend la rechaza. Aqui se pide entera para
 * que el gestor no descubra el error despues de escribir la observacion.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { Cliente, FilaGestion, NuevaGestion } from "../api/cliente";
import { Superficie } from "./Superficie";

const TIPOS = [
  { valor: "llamada", etiqueta: "Llamada" },
  { valor: "correo", etiqueta: "Correo" },
  { valor: "mensaje", etiqueta: "Mensaje" },
  { valor: "visita", etiqueta: "Visita" },
  { valor: "acuerdo", etiqueta: "Acuerdo de pago" },
  { valor: "disputa", etiqueta: "Disputa" },
  { valor: "otra", etiqueta: "Otra" },
] as const;

const CAMPO =
  "w-full rounded-lg border border-filete px-2 py-1 text-base text-tinta transition-colors duration-estado placeholder:text-tenue focus:border-[#2F6B9A] focus:outline-none";

export function RegistrarGestion({
  cliente,
  nit,
  alertas,
}: {
  cliente: Cliente;
  nit: string;
  alertas: FilaGestion[];
}) {
  const [factura, setFactura] = useState("");
  const [tipo, setTipo] = useState<string>("llamada");
  const [resultado, setResultado] = useState("");
  const [observacion, setObservacion] = useState("");
  const [conCompromiso, setConCompromiso] = useState(false);
  const [compromisoFecha, setCompromisoFecha] = useState("");
  const [compromisoValor, setCompromisoValor] = useState("");

  const consultas = useQueryClient();
  const guardar = useMutation({
    mutationFn: (gestion: NuevaGestion) => cliente.registrarGestion(nit, gestion),
    onSuccess: () => {
      consultas.invalidateQueries({ queryKey: ["cliente", nit] });
      consultas.invalidateQueries({ queryKey: ["gestion"] });
      setResultado("");
      setObservacion("");
      setConCompromiso(false);
      setCompromisoFecha("");
      setCompromisoValor("");
    },
  });

  // Solo las facturas con alerta admiten gestion: el backend rechaza el resto.
  const facturas = [...new Set(alertas.map((a) => a.factura).filter(Boolean))];

  const compromisoIncompleto =
    conCompromiso && (!compromisoFecha || !compromisoValor);

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    guardar.mutate({
      factura,
      tipo,
      // El usuario no se envia: el servidor lo toma del token. §10.3 exige un
      // rastro fiable, y uno que el cliente firma a su gusto no lo es.
      resultado: resultado || null,
      observacion: observacion || null,
      compromiso_fecha: conCompromiso ? compromisoFecha : null,
      compromiso_valor: conCompromiso ? compromisoValor : null,
    });
  }

  return (
    <Superficie titulo="Registrar gestión">
      <form onSubmit={enviar} className="space-y-entre">
        <div className="grid gap-entre md:grid-cols-3">
          <label className="text-menor text-apagado">
            Factura
            <select
              value={factura}
              onChange={(e) => setFactura(e.target.value)}
              className={`mt-1 ${CAMPO}`}
            >
              <option value="">Todo el cliente</option>
              {facturas.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>

          <label className="text-menor text-apagado">
            Tipo
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className={`mt-1 ${CAMPO}`}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </select>
          </label>

          <label className="text-menor text-apagado">
            Resultado
            <input
              value={resultado}
              onChange={(e) => setResultado(e.target.value)}
              placeholder="Contactado, sin respuesta…"
              className={`mt-1 ${CAMPO}`}
            />
          </label>
        </div>

        <label className="block text-menor text-apagado">
          Observación
          <textarea
            value={observacion}
            onChange={(e) => setObservacion(e.target.value)}
            rows={2}
            className={`mt-1 ${CAMPO}`}
          />
        </label>

        <label className="flex items-center gap-1.5 text-base text-apagado">
          <input
            type="checkbox"
            checked={conCompromiso}
            onChange={(e) => setConCompromiso(e.target.checked)}
          />
          Hubo compromiso de pago
        </label>

        {conCompromiso && (
          <div className="grid gap-entre md:grid-cols-2">
            <label className="text-menor text-apagado">
              Fecha comprometida
              <input
                type="date"
                value={compromisoFecha}
                onChange={(e) => setCompromisoFecha(e.target.value)}
                className={`mt-1 ${CAMPO}`}
              />
            </label>
            <label className="text-menor text-apagado">
              Valor comprometido
              <input
                type="number"
                min="1"
                value={compromisoValor}
                onChange={(e) => setCompromisoValor(e.target.value)}
                className={`mt-1 ${CAMPO}`}
              />
            </label>
          </div>
        )}

        <div className="flex items-center gap-entre">
          <button
            type="submit"
            disabled={guardar.isPending || compromisoIncompleto}
            className="rounded-lg bg-[#2F6B9A] px-3 py-1.5 text-base font-medium text-white transition-colors duration-estado disabled:opacity-40"
          >
            {guardar.isPending ? "Guardando…" : "Registrar"}
          </button>
          {compromisoIncompleto && (
            <span className="text-menor text-apagado">
              Un compromiso necesita fecha y valor.
            </span>
          )}
          {guardar.isError && (
            <span className="text-menor text-[#9B1C1C]">
              {(guardar.error as Error).message}
            </span>
          )}
          {guardar.isSuccess && !guardar.isPending && (
            <span className="text-menor text-[#2F6B9A]">Gestión registrada.</span>
          )}
        </div>
      </form>
    </Superficie>
  );
}
