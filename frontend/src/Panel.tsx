/**
 * Panel de control (§8.1), etapa 4 del plan.
 *
 * El objetivo declarado es responder en cinco segundos: como esta la cartera y
 * a quien llamo hoy. Por eso todo el panel llega en una sola peticion y no en
 * cuatro que el navegador tendria que coordinar.
 *
 * Aqui no hay logica de negocio. Los porcentajes, las prioridades y los colores
 * vienen calculados del API: §16 exige una sola fuente de calculo, y recalcular
 * cualquiera de ellos en el navegador seria una segunda implementacion que
 * podria divergir del PDF y del Excel.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { Cliente } from "./api/cliente";
import { GraficoAging } from "./componentes/GraficoAging";
import { Cargando, Fallo } from "./componentes/Estados";
import { Ranking } from "./componentes/Ranking";
import { SelectorCorte } from "./componentes/SelectorCorte";
import { TarjetasKPI } from "./componentes/TarjetasKPI";
import { Superficie } from "./componentes/Superficie";
import { fecha } from "./formato";

export function Panel({
  cliente,
  onAbrirCliente,
}: {
  cliente: Cliente;
  onAbrirCliente?: (nit: string) => void;
}) {
  const [corte, setCorte] = useState<string | undefined>();

  const cortes = useQuery({
    queryKey: ["cortes"],
    queryFn: () => cliente.cortes(),
  });

  const panel = useQuery({
    queryKey: ["panel", corte],
    queryFn: () => cliente.panel(corte),
    // Mantener el tablero anterior mientras llega el nuevo es lo que permite
    // mover la fecha de corte sin que la pantalla parpadee (§7.4).
    placeholderData: (previo) => previo,
  });

  if (panel.isPending) return <Cargando que="el panel" />;
  if (panel.isError) return <Fallo error={panel.error} />;

  const datos = panel.data;

  return (
    <div className="mx-auto max-w-[1400px] space-y-entre p-marco">
      <header className="flex flex-wrap items-baseline justify-between gap-entre">
        <div>
          <h1 className="text-titulo font-semibold tracking-tight text-tinta">
            Cartera
          </h1>
          <p className="text-menor text-tenue">
            Corte {fecha(datos.corte)} · {datos.n_clientes} clientes ·{" "}
            {datos.n_facturas} facturas
            {panel.isFetching && " · actualizando…"}
          </p>
        </div>
        <SelectorCorte
          cortes={cortes.data ?? []}
          valor={corte ?? datos.corte}
          onCambiar={setCorte}
        />
      </header>

      <TarjetasKPI kpis={datos.kpis} />

      <div className="grid items-start gap-entre lg:grid-cols-[1fr_1.2fr]">
        <GraficoAging aging={datos.aging} />
        <Ranking clientes={datos.ranking} onAbrir={onAbrirCliente ?? (() => {})} />
      </div>

      <ReglasPendientes reglas={datos.reglas_inactivas ?? {}} />
    </div>
  );
}

/**
 * Aviso de reglas que no se estan evaluando (§8.4).
 *
 * Es lo que evita el peor modo de fallo de este tipo de modulo: que una regla
 * este apagada por falta de umbral y nadie se entere, de modo que el panel
 * parezca completo mientras deja pasar alertas.
 */
function ReglasPendientes({ reglas }: { reglas: Record<string, string> }) {
  const codigos = Object.keys(reglas);
  if (codigos.length === 0) return null;

  return (
    <Superficie titulo="Reglas sin evaluar">
      <ul className="space-y-1 text-base text-apagado">
        {codigos.map((codigo) => (
          <li key={codigo}>
            <span className="font-semibold text-tinta">{codigo}</span>{" "}
            {reglas[codigo]}
          </li>
        ))}
      </ul>
    </Superficie>
  );
}
