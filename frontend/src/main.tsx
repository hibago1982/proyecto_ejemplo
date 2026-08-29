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

// Provisional, igual que en el backend: cuando exista autenticacion tanto la
// empresa como el usuario saldran de la sesion y no de variables de arranque.
// El usuario importa mas de lo que parece: §10.3 exige registrar quien hizo
// cada gestion, y un rastro firmado por "sin_identificar" no sirve de nada.
const EMPRESA_ID = import.meta.env["VITE_EMPRESA_ID"] ?? "E01";
const USUARIO_ID = import.meta.env["VITE_USUARIO_ID"] ?? "demo";

const cliente = crearCliente({ empresaId: EMPRESA_ID });

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <App cliente={cliente} usuarioId={USUARIO_ID} />
    </QueryClientProvider>
  </StrictMode>,
);
