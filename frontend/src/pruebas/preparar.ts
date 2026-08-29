import "@testing-library/jest-dom/vitest";

/**
 * jsdom no implementa ResizeObserver, y el ResponsiveContainer de Recharts lo
 * necesita para medir su contenedor. Sin este doble, cualquier prueba que monte
 * el grafico de aging falla por un motivo que no tiene que ver con lo que se
 * esta probando.
 */
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverFalso as unknown as typeof ResizeObserver;
