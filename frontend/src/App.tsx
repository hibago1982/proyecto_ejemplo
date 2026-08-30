/**
 * Armazon de la aplicacion: navegacion entre las tres pantallas de §8.
 *
 * §7.1 pide "un clic hasta la accion": indicador -> cliente -> factura, sin
 * menus intermedios. Por eso la barra es una sola linea y el drill-down ocurre
 * pulsando una fila, no navegando por un arbol.
 */
import type { Cliente, Sesion } from "./api/cliente";
import { Exportar } from "./componentes/Exportar";
import { DetalleCliente } from "./DetalleCliente";
import { ListaGestion } from "./ListaGestion";
import { Panel } from "./Panel";
import { irA, rutaDe, useVista, type Vista } from "./navegacion";

const PESTANAS: { vista: Vista; etiqueta: string }[] = [
  { vista: { nombre: "panel" }, etiqueta: "Panel" },
  { vista: { nombre: "gestion" }, etiqueta: "Lista de gestión" },
];

export function App({
  cliente,
  sesion,
  onSalir,
}: {
  cliente: Cliente;
  sesion: Sesion;
  onSalir: () => void;
}) {
  const vista = useVista();

  return (
    <>
      <nav className="border-b border-filete bg-white">
        <div className="mx-auto flex max-w-[1400px] items-center gap-entre px-marco">
          <span className="py-2.5 text-menor font-semibold uppercase tracking-widest text-[#2F6B9A]">
            Busint
          </span>
          {PESTANAS.map(({ vista: destino, etiqueta }) => {
            const activa = destino.nombre === vista.nombre;
            return (
              <a
                key={etiqueta}
                href={rutaDe(destino)}
                aria-current={activa ? "page" : undefined}
                className={`border-b-2 py-2.5 text-base transition-colors duration-estado ${
                  activa
                    ? "border-[#2F6B9A] font-medium text-tinta"
                    : "border-transparent text-apagado hover:text-tinta"
                }`}
              >
                {etiqueta}
              </a>
            );
          })}

          <div className="ml-auto flex items-center gap-entre text-menor text-apagado">
            <Exportar cliente={cliente} />
            <span className="text-tenue">
              {sesion.nombre || sesion.usuario_id} · {sesion.rol_etiqueta}
            </span>
            <button
              type="button"
              onClick={onSalir}
              className="transition-colors duration-estado hover:text-tinta"
            >
              Salir
            </button>
          </div>
        </div>
      </nav>

      {vista.nombre === "cliente" ? (
        <DetalleCliente cliente={cliente} nit={vista.nit} />
      ) : vista.nombre === "gestion" ? (
        <ListaGestion cliente={cliente} />
      ) : (
        <Panel
          cliente={cliente}
          onAbrirCliente={(nit) => irA({ nombre: "cliente", nit })}
        />
      )}
    </>
  );
}
