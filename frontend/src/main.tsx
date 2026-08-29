import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { crearCliente } from "./api/cliente";
import { App } from "./App";
import "./estilos.css";

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

// Provisional, igual que en el backend: cuando exista autenticacion la empresa
// saldra de la sesion del usuario y no de una variable de arranque.
const cliente = crearCliente({
  empresaId: import.meta.env["VITE_EMPRESA_ID"] ?? "E01",
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <App cliente={cliente} />
    </QueryClientProvider>
  </StrictMode>,
);
