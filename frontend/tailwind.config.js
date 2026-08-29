/** Sistema de diseño de §7.2.
 *
 * No es una eleccion estetica suelta: la reticula, la escala tipografica y la
 * superficie estan fijadas en la especificacion para que cualquier pantalla
 * futura del ERP se vea coherente con esta.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      spacing: {
        // Base de 4 px: margenes 20, separacion entre tarjetas 12, relleno 16.
        marco: "20px",
        entre: "12px",
        dentro: "16px",
      },
      borderRadius: { tarjeta: "16px" },
      fontSize: {
        // Escala compacta de 10 a 22. La jerarquia se hace con peso y color,
        // no con tamaño, para mostrar mas informacion sin densidad visual.
        micro: ["10px", "14px"],
        menor: ["11px", "16px"],
        base: ["13px", "18px"],
        medio: ["15px", "20px"],
        mayor: ["18px", "24px"],
        titulo: ["22px", "28px"],
      },
      colors: {
        filete: "#E8EAED",
        tinta: "#1A1D21",
        apagado: "#6B7280",
        tenue: "#9CA3AF",
      },
      transitionDuration: { estado: "150ms" },
    },
  },
  plugins: [],
};
