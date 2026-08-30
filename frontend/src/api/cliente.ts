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
export type Sesion = components["schemas"]["Sesion"];

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
  token: () => string | null;
  alCaducar?: () => void;
}

export function crearCliente({
  base = "/api/v1",
  token,
  alCaducar,
}: OpcionesCliente) {
  async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
    const actual = token();
    const respuesta = await fetch(`${base}${ruta}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        // La empresa y el rol van dentro del token, firmados. Ya no viajan como
        // cabecera editable.
        ...(actual ? { Authorization: `Bearer ${actual}` } : {}),
        ...init?.headers,
      },
    });

    if (respuesta.status === 401) {
      // El token caduco o fue revocado: se vuelve al inicio de sesion en vez de
      // dejar la pantalla con un error que el usuario no puede resolver.
      alCaducar?.();
    }

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
    entrar: (usuario: string, clave: string) =>
      pedir<Sesion>("/sesion", {
        method: "POST",
        body: JSON.stringify({ usuario, clave }),
      }),
    quienSoy: () => pedir<Sesion>("/sesion"),
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
    /**
     * Descarga una exportacion.
     *
     * No se puede usar un enlace normal: `<a href>` no lleva cabeceras, asi que
     * el navegador pediria el archivo sin token y recibiria un 401. Y meter el
     * token en la URL lo dejaria en el historial y en los registros del
     * servidor. Se pide con fetch autenticado y se entrega como blob.
     */
    descargar: async (formato: "excel" | "pdf", corte?: string) => {
      const actual = token();
      const respuesta = await fetch(conCorte(`${base}/exportar/${formato}`, corte), {
        headers: actual ? { Authorization: `Bearer ${actual}` } : {},
      });
      if (!respuesta.ok) {
        if (respuesta.status === 401) alCaducar?.();
        const cuerpo = await respuesta.json().catch(() => null);
        throw new ErrorApi(
          respuesta.status,
          cuerpo?.detail ?? `No se pudo generar el ${formato}.`,
        );
      }
      const nombre =
        /filename="([^"]+)"/.exec(
          respuesta.headers.get("Content-Disposition") ?? "",
        )?.[1] ?? `cartera.${formato === "excel" ? "xlsx" : "pdf"}`;
      return { blob: await respuesta.blob(), nombre };
    },
    registrarGestion: (nit: string, gestion: NuevaGestion) =>
      pedir<Gestion>(`/clientes/${encodeURIComponent(nit)}/gestiones`, {
        method: "POST",
        body: JSON.stringify(gestion),
      }),
  };
}

export type Cliente = ReturnType<typeof crearCliente>;
