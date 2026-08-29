import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Recharts pesa mas que todo el resto junto. Separarlo permite que el
        // navegador cachee React y la libreria de graficos entre despliegues,
        // en vez de volver a bajar 800 kB por cada cambio de una etiqueta.
        manualChunks: {
          react: ["react", "react-dom"],
          graficos: ["recharts"],
          datos: ["@tanstack/react-query"],
        },
      },
    },
  },
  server: {
    // El frontend no lleva logica de negocio ni credenciales: todo pasa por el
    // API, que es la unica fuente de calculo (§16).
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/pruebas/preparar.ts"],
  },
});
