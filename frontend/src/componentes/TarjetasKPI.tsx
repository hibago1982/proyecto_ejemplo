/**
 * Tarjetas del encabezado (§8.1).
 *
 * "Vence hoy" aparece como indicador propio y no dentro de vencida: es la
 * correccion C-14, sin la cual los tres indicadores no suman el total. Sobre el
 * archivo de prueba son 84,5 de 506,4 millones, el 16,7 % de la cartera que el
 * informe anterior reportaba como vencida sin estarlo.
 */
import type { TarjetaKPI } from "../api/cliente";
import { pesos, porcentaje } from "../formato";
import { Superficie } from "./Superficie";

export function TarjetasKPI({ kpis }: { kpis: TarjetaKPI[] }) {
  return (
    <div className="grid grid-cols-2 gap-entre md:grid-cols-5">
      {kpis.map((kpi) => (
        <Superficie key={kpi.codigo}>
          <p className="text-menor font-medium uppercase tracking-wide text-apagado">
            {kpi.etiqueta}
          </p>
          <p className="mt-1 text-mayor font-semibold tabular-nums text-tinta">
            {pesos(kpi.valor)}
          </p>
          {kpi.codigo !== "cartera_total" && (
            <p className="mt-0.5 text-menor tabular-nums text-tenue">
              {porcentaje(kpi.pct_sobre_total)} del total
            </p>
          )}
        </Superficie>
      ))}
    </div>
  );
}
