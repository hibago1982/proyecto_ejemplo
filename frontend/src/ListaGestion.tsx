/**
 * Lista de gestion (§8.2), etapa 5.
 *
 * §7.1 lo resume: el usuario no lee la cartera, la trabaja. Cada fila lleva su
 * accion sugerida y su explicacion, de modo que no haya que interpretar nada
 * para saber que hacer.
 *
 * Los filtros y el orden viajan al API y no se aplican en el navegador: la
 * lista real tiene cientos de miles de facturas y traerlas todas para filtrar
 * aqui seria insostenible, ademas de duplicar criterios que ya estan probados
 * en el backend.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { Cliente, FilaGestion } from "./api/cliente";
import { Chip } from "./componentes/Chip";
import { Cargando, Fallo } from "./componentes/Estados";
import { Explicacion } from "./componentes/Explicacion";
import { Superficie } from "./componentes/Superficie";
import { dias, fecha, pesos } from "./formato";
import { irA } from "./navegacion";

type Orden = "prioridad" | "dias" | "saldo" | "cliente";

/** Filtros rapidos de §8.2: prioritarias, criticas y por vencer. */
const RAPIDOS = [
  { id: "todas", etiqueta: "Todas", parametros: {} },
  { id: "prioritarias", etiqueta: "Prioritarias", parametros: { prioridad_minima: 2 } },
  { id: "criticas", etiqueta: "Críticas", parametros: { prioridad_minima: 4 } },
  { id: "por_vencer", etiqueta: "Por vencer", parametros: { bucket: "B00" } },
] as const;

const POR_PAGINA = 40;

export function ListaGestion({ cliente }: { cliente: Cliente }) {
  const [rapido, setRapido] = useState<string>("todas");
  const [busqueda, setBusqueda] = useState("");
  const [orden, setOrden] = useState<Orden>("prioridad");
  const [pagina, setPagina] = useState(1);

  const filtro = RAPIDOS.find((f) => f.id === rapido) ?? RAPIDOS[0];

  const lista = useQuery({
    queryKey: ["gestion", rapido, busqueda, orden, pagina],
    queryFn: () =>
      cliente.gestion({
        ...filtro.parametros,
        busqueda: busqueda.trim() || undefined,
        orden,
        pagina,
        por_pagina: POR_PAGINA,
      }),
    // Sin esto la tabla parpadea en blanco al cambiar de filtro o de pagina.
    placeholderData: keepPreviousData,
  });

  function cambiarFiltro(id: string) {
    setRapido(id);
    setPagina(1);
  }

  if (lista.isPending) return <Cargando que="la lista de gestión" />;
  if (lista.isError) return <Fallo error={lista.error} />;

  const datos = lista.data;
  const paginas = Math.max(1, Math.ceil(datos.total / POR_PAGINA));

  return (
    <div className="mx-auto max-w-[1400px] space-y-entre p-marco">
      <header>
        <h1 className="text-titulo font-semibold tracking-tight text-tinta">
          Lista de gestión
        </h1>
        <p className="text-menor text-tenue">
          {datos.total} alertas activas · corte {fecha(datos.corte)}
          {lista.isFetching && " · actualizando…"}
        </p>
      </header>

      <Superficie>
        <div className="flex flex-wrap items-center gap-entre">
          <div className="flex gap-1" role="group" aria-label="Filtros rápidos">
            {RAPIDOS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => cambiarFiltro(f.id)}
                aria-pressed={rapido === f.id}
                className={`rounded-lg border px-2.5 py-1 text-base transition-colors duration-estado ${
                  rapido === f.id
                    ? "border-[#2F6B9A] bg-[#2F6B9A] text-white"
                    : "border-filete bg-white text-apagado hover:border-apagado"
                }`}
              >
                {f.etiqueta}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={busqueda}
            onChange={(e) => {
              setBusqueda(e.target.value);
              setPagina(1);
            }}
            placeholder="Buscar por NIT o factura"
            aria-label="Buscar por NIT o factura"
            className="min-w-[220px] flex-1 rounded-lg border border-filete px-2.5 py-1 text-base text-tinta transition-colors duration-estado placeholder:text-tenue focus:border-[#2F6B9A] focus:outline-none"
          />

          <label className="flex items-center gap-1.5 text-base">
            <span className="text-menor uppercase tracking-wide text-apagado">
              Orden
            </span>
            <select
              value={orden}
              onChange={(e) => setOrden(e.target.value as Orden)}
              className="rounded-lg border border-filete bg-white px-2 py-1 text-base text-tinta focus:border-[#2F6B9A] focus:outline-none"
            >
              <option value="prioridad">Prioridad</option>
              <option value="dias">Días</option>
              <option value="saldo">Saldo</option>
              <option value="cliente">Cliente</option>
            </select>
          </label>
        </div>
      </Superficie>

      {datos.filas.length === 0 ? (
        <Superficie>
          <p className="py-8 text-center text-base text-tenue">
            {busqueda
              ? `Ninguna alerta coincide con «${busqueda}».`
              : "No hay alertas con este filtro."}
          </p>
        </Superficie>
      ) : (
        <Superficie className="overflow-x-auto">
          <table className="w-full text-base">
            <thead>
              <tr className="border-b border-filete text-menor uppercase tracking-wide text-tenue">
                <th className="py-1.5 text-left font-medium">Alerta</th>
                <th className="py-1.5 text-left font-medium">Cliente</th>
                <th className="py-1.5 text-left font-medium">Factura</th>
                <th className="py-1.5 text-right font-medium">Días</th>
                <th className="py-1.5 pr-3 text-right font-medium">Saldo</th>
                <th className="py-1.5 text-left font-medium">Prioridad</th>
                <th className="py-1.5 text-left font-medium">Acción sugerida</th>
              </tr>
            </thead>
            <tbody>
              {datos.filas.map((fila) => (
                <Fila key={fila.id} fila={fila} />
              ))}
            </tbody>
          </table>
        </Superficie>
      )}

      {paginas > 1 && (
        <nav className="flex items-center justify-between text-base" aria-label="Paginación">
          <button
            type="button"
            disabled={pagina <= 1}
            onClick={() => setPagina((p) => p - 1)}
            className="rounded-lg border border-filete px-2.5 py-1 text-apagado transition-colors duration-estado disabled:opacity-40 enabled:hover:border-apagado"
          >
            Anterior
          </button>
          <span className="text-menor text-tenue">
            Página {pagina} de {paginas}
          </span>
          <button
            type="button"
            disabled={pagina >= paginas}
            onClick={() => setPagina((p) => p + 1)}
            className="rounded-lg border border-filete px-2.5 py-1 text-apagado transition-colors duration-estado disabled:opacity-40 enabled:hover:border-apagado"
          >
            Siguiente
          </button>
        </nav>
      )}
    </div>
  );
}

function Fila({ fila }: { fila: FilaGestion }) {
  return (
    <tr
      onClick={() => irA({ nombre: "cliente", nit: fila.cliente_nit })}
      tabIndex={0}
      role="button"
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          irA({ nombre: "cliente", nit: fila.cliente_nit });
        }
      }}
      className="cursor-pointer border-b border-filete/60 transition-colors duration-estado last:border-0 hover:bg-[#FAFBFC] focus:bg-[#F2F6FA] focus:outline-none"
    >
      <td className="py-2 pr-2">
        <span className="flex items-center gap-1.5">
          <span className="font-medium text-tinta">{fila.codigo}</span>
          <Explicacion texto={fila.explicacion} />
        </span>
        <span className="text-menor text-tenue">{fila.etiqueta}</span>
      </td>
      <td className="py-2 pr-2">
        <span className="block max-w-[240px] truncate text-tinta">
          {fila.cliente_nombre || fila.cliente_nit}
        </span>
        {fila.cliente_nombre && (
          <span className="text-menor tabular-nums text-tenue">{fila.cliente_nit}</span>
        )}
      </td>
      <td className="py-2 pr-2 tabular-nums text-apagado">{fila.factura || "—"}</td>
      <td className="py-2 text-right tabular-nums text-apagado">{dias(fila.dias)}</td>
      <td className="py-2 pr-3 text-right tabular-nums text-tinta">
        {fila.saldo ? pesos(fila.saldo) : "—"}
      </td>
      <td className="py-2 pl-2">
        <Chip nivel={fila.prioridad} texto={fila.prioridad_etiqueta} />
      </td>
      <td className="py-2 pl-2 text-apagado">{fila.accion}</td>
    </tr>
  );
}
