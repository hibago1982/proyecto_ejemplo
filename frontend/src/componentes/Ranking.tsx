/**
 * Ranking de clientes que requieren atencion (§8.1).
 *
 * §7.1 "de informe a lista de trabajo": cada fila es accionable y lleva al
 * detalle del cliente en un clic, sin menus intermedios.
 */
import type { ClienteEnRanking } from "../api/cliente";
import { pesos, porcentaje } from "../formato";
import { Chip } from "./Chip";
import { Superficie } from "./Superficie";

const MARCADORES: Record<string, string> = {
  M04: "Envejecimiento",
  M05: "Riesgo crítico",
};

export function Ranking({
  clientes,
  onAbrir,
}: {
  clientes: ClienteEnRanking[];
  onAbrir: (nit: string) => void;
}) {
  if (clientes.length === 0) {
    return (
      <Superficie titulo="Clientes que requieren atención">
        <p className="py-6 text-center text-base text-tenue">
          Ningún cliente supera los umbrales configurados.
        </p>
      </Superficie>
    );
  }

  return (
    <Superficie titulo="Clientes que requieren atención">
      <table className="w-full text-base">
        <thead>
          <tr className="border-b border-filete text-menor uppercase tracking-wide text-tenue">
            <th className="py-1.5 text-left font-medium">Cliente</th>
            <th className="py-1.5 text-right font-medium">Cartera</th>
            <th className="py-1.5 text-right font-medium">Vencida</th>
            <th className="py-1.5 text-right font-medium">&gt;90</th>
            <th className="py-1.5 text-right font-medium">Máx</th>
            <th className="py-1.5 text-left font-medium">Prioridad</th>
          </tr>
        </thead>
        <tbody>
          {clientes.map((c) => (
            <tr
              key={c.cliente_nit}
              onClick={() => onAbrir(c.cliente_nit)}
              tabIndex={0}
              role="button"
              onKeyDown={(e) => {
                // §16 exige navegacion completa por teclado, no solo por raton.
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onAbrir(c.cliente_nit);
                }
              }}
              className="cursor-pointer border-b border-filete/60 transition-colors duration-estado last:border-0 hover:bg-[#FAFBFC] focus:bg-[#F2F6FA] focus:outline-none"
            >
              <td className="py-2 pr-2">
                <p className="font-medium text-tinta">{c.cliente_nombre || c.cliente_nit}</p>
                <p className="text-menor text-tenue">
                  {c.cliente_nit}
                  {(c.marcadores?.length ?? 0) > 0 &&
                    ` · ${c.marcadores!.map((m) => MARCADORES[m] ?? m).join(", ")}`}
                </p>
              </td>
              <td className="py-2 text-right tabular-nums text-tinta">
                {pesos(c.cartera_total)}
              </td>
              <td className="py-2 text-right tabular-nums text-apagado">
                {porcentaje(c.pct_vencida)}
              </td>
              <td className="py-2 text-right tabular-nums text-apagado">
                {porcentaje(c.pct_90)}
              </td>
              <td className="py-2 text-right tabular-nums text-apagado">
                {c.dias_max} d
              </td>
              <td className="py-2 pl-2">
                <Chip nivel={c.prioridad} texto={c.prioridad_etiqueta} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Superficie>
  );
}
