/**
 * Selector de fecha de corte.
 *
 * §7.4 lo llama "fecha de corte en vivo" y es el elemento diferenciador
 * principal: moverla recalcula el tablero entero. Por eso es un control del
 * encabezado y no una opcion escondida en un filtro.
 *
 * Solo ofrece cortes ya calculados. Un corte que no existe no se puede
 * reproducir desde el ERP (C-16), asi que dejar escribir una fecha libre seria
 * ofrecer algo que el sistema no puede cumplir.
 */
import type { Corte } from "../api/cliente";
import { fecha, pesosCompactos } from "../formato";

export function SelectorCorte({
  cortes,
  valor,
  onCambiar,
}: {
  cortes: Corte[];
  valor: string | undefined;
  onCambiar: (corte: string) => void;
}) {
  if (cortes.length === 0) return null;

  return (
    <label className="flex items-center gap-2 text-base">
      <span className="text-menor uppercase tracking-wide text-apagado">Corte</span>
      <select
        value={valor ?? cortes[0]!.corte}
        onChange={(e) => onCambiar(e.target.value)}
        className="rounded-lg border border-filete bg-white px-2 py-1 text-base tabular-nums text-tinta transition-colors duration-estado focus:border-[#2F6B9A] focus:outline-none"
      >
        {cortes.map((c) => (
          <option key={c.corte} value={c.corte}>
            {fecha(c.corte)} · {pesosCompactos(c.cartera_total)} · {c.n_clientes} clientes
          </option>
        ))}
      </select>
    </label>
  );
}
