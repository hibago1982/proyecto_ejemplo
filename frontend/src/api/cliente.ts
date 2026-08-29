/**
 * Cliente del API.
 *
 * Los tipos no se escriben a mano: salen de `tipos.ts`, que genera
 * openapi-typescript desde el contrato del backend. Es lo que hace que un
 * cambio incompatible en el API rompa la compilacion aqui en vez de fallar en
 * silencio delante del usuario (§5).
 */
import type { components } from "./tipos";

export type Panel = components["schemas"]["Panel"];
export type TarjetaKPI = components["schemas"]["TarjetaKPI"];
export type BarraAging = components["schemas"]["BarraAging"];
export type ClienteEnRanking = components["schemas"]["ClienteEnRanking"];
export type ListaGestion = components["schemas"]["ListaGestion"];
export type FilaGestion = components["schemas"]["FilaGestion"];
export type DetalleCliente = components["schemas"]["DetalleCliente"];
export type Configuracion = components["schemas"]["Configuracion"];
export type ReglaConfigurada = components["schemas"]["ReglaConfigurada"];
export type Corte = components["schemas"]["Corte"];
export type Gestion = components["schemas"]["Gestion"];
export type NuevaGestion = components["schemas"]["NuevaGestion"];

export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }
}

export interface OpcionesCliente {
  base?: string;
  empresaId: string;
}

export function crearCliente({ base = "/api/v1", empresaId }: OpcionesCliente) {
  async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
    const respuesta = await fetch(`${base}${ruta}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        // Provisional, igual que en el backend: cuando exista autenticacion
        // esto sale del token y no de la peticion.
        "X-Empresa-Id": empresaId,
        ...init?.headers,
      },
    });

    if (!respuesta.ok) {
      // El detalle del backend es legible y esta pensado para mostrarse tal
      // cual: dice si hay que revisar el ERP, la configuracion o el corte.
      const cuerpo = await respuesta.json().catch(() => null);
      throw new ErrorApi(
        respuesta.status,
        cuerpo?.detail ?? `El servidor respondio ${respuesta.status}.`,
      );
    }
    return respuesta.json() as Promise<T>;
  }

  const conCorte = (ruta: string, corte?: string) =>
    corte ? `${ruta}${ruta.includes("?") ? "&" : "?"}corte=${corte}` : ruta;

  return {
    cortes: () => pedir<Corte[]>("/cortes"),
    panel: (corte?: string) => pedir<Panel>(conCorte("/panel", corte)),
    gestion: (parametros: Record<string, string | number | undefined>) => {
      const busqueda = new URLSearchParams();
      for (const [clave, valor] of Object.entries(parametros)) {
        if (valor !== undefined && valor !== "") busqueda.set(clave, String(valor));
      }
      return pedir<ListaGestion>(`/gestion?${busqueda}`);
    },
    cliente: (nit: string, corte?: string) =>
      pedir<DetalleCliente>(conCorte(`/clientes/${encodeURIComponent(nit)}`, corte)),
    configuracion: () => pedir<Configuracion>("/configuracion"),
    registrarGestion: (nit: string, gestion: NuevaGestion) =>
      pedir<Gestion>(`/clientes/${encodeURIComponent(nit)}/gestiones`, {
        method: "POST",
        body: JSON.stringify(gestion),
      }),
  };
}

export type Cliente = ReturnType<typeof crearCliente>;
