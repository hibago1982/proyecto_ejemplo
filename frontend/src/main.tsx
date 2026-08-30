import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useCallback, useState } from "react";
import { createRoot } from "react-dom/client";

import { crearCliente, type Sesion } from "./api/cliente";
import { App } from "./App";
import { Entrar } from "./Entrar";
import "./estilos.css";

const CLAVE_SESION = "busint.sesion";

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      // El corte es un dato del dia: no tiene sentido reconsultarlo al volver
      // a la pestana. Cuando el motor corre, el usuario cambia de corte.
      refetchOnWindowFocus: false,
      staleTime: 60_000,
      retry: 1,
    },
  },
});

function leerSesion(): Sesion | null {
  try {
    const guardada = localStorage.getItem(CLAVE_SESION);
    if (!guardada) return null;
    const sesion = JSON.parse(guardada) as Sesion;
    // Un token caducado no sirve: mejor pedir la clave que dejar al usuario
    // ante una pantalla de errores que no puede resolver.
    return new Date(sesion.expira) > new Date() ? sesion : null;
  } catch {
    return null;
  }
}

function Raiz() {
  const [sesion, setSesion] = useState<Sesion | null>(leerSesion);

  const salir = useCallback(() => {
    localStorage.removeItem(CLAVE_SESION);
    setSesion(null);
    clienteConsultas.clear();
  }, []);

  const guardar = useCallback((nueva: Sesion) => {
    localStorage.setItem(CLAVE_SESION, JSON.stringify(nueva));
    setSesion(nueva);
  }, []);

  const cliente = crearCliente({
    token: () => leerSesion()?.token ?? null,
    alCaducar: salir,
  });

  if (!sesion) return <Entrar cliente={cliente} onEntrar={guardar} />;
  return <App cliente={cliente} sesion={sesion} onSalir={salir} />;
}

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <Raiz />
    </QueryClientProvider>
  </StrictMode>,
);
