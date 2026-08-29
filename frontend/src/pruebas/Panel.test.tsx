/**
 * Pruebas del panel.
 *
 * Se centran en lo que puede romperse en silencio: que las cifras se muestren
 * sin perder precision, que "vence hoy" aparezca separado (C-14), y que las
 * reglas apagadas se vean en pantalla en vez de quedar ocultas.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Cliente } from "../api/cliente";
import { Panel } from "../Panel";
import { CORTES, PANEL } from "./datos";

/** Intl usa espacio duro entre el simbolo y la cifra. */
const monto = (texto: string) => new RegExp(texto.replace(/\./g, "\\."));

function montar(sobrescribir: Partial<Cliente> = {}) {
  const cliente = {
    cortes: vi.fn().mockResolvedValue(CORTES),
    panel: vi.fn().mockResolvedValue(PANEL),
    gestion: vi.fn(),
    cliente: vi.fn(),
    configuracion: vi.fn(),
    ...sobrescribir,
  } as unknown as Cliente;

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={qc}>
      <Panel cliente={cliente} />
    </QueryClientProvider>,
  );
  return cliente;
}

describe("Panel de control", () => {
  it("muestra las cinco tarjetas de §8.1", async () => {
    montar();
    await waitFor(() => expect(screen.getByText("Cartera total")).toBeInTheDocument());
    for (const etiqueta of ["Por vencer", "Vence hoy", "Vencida", "Mas de 90 dias"]) {
      expect(screen.getAllByText(etiqueta).length).toBeGreaterThan(0);
    }
  });

  it("presenta 'vence hoy' como indicador propio (C-14)", async () => {
    montar();
    await waitFor(() => expect(screen.getAllByText("Vence hoy").length).toBeGreaterThan(0));
    // 84,5 millones que el informe anterior contaba como vencidos sin estarlo.
    expect(screen.getByText(monto("84.500.000"))).toBeInTheDocument();
  });

  it("formatea los montos sin perder pesos", async () => {
    montar();
    await waitFor(() =>
      expect(screen.getByText(monto("506.400.000"))).toBeInTheDocument(),
    );
  });

  it("avisa de las reglas que no se estan evaluando", async () => {
    montar();
    await waitFor(() => expect(screen.getByText("Reglas sin evaluar")).toBeInTheDocument());
    expect(screen.getByText("R01")).toBeInTheDocument();
    expect(
      screen.getByText(/no ha asignado valor a: umbral_saldo_alto/),
    ).toBeInTheDocument();
  });

  it("lista el cliente del ranking con su prioridad", async () => {
    montar();
    await waitFor(() =>
      expect(screen.getByText("TEXTILES DE ANTIOQUIA SAS")).toBeInTheDocument(),
    );
    expect(screen.getByText("Muy alta")).toBeInTheDocument();
    // El marcador se muestra con nombre legible, no con su codigo interno.
    expect(screen.getByText(/Envejecimiento/)).toBeInTheDocument();
  });

  it("muestra el mensaje del backend cuando falla", async () => {
    montar({
      panel: vi
        .fn()
        .mockRejectedValue(new Error("La empresa 'E01' no tiene ningun corte calculado.")),
    });
    await waitFor(() =>
      expect(screen.getByText(/no tiene ningun corte calculado/)).toBeInTheDocument(),
    );
  });

  it("pide el panel al API una sola vez", async () => {
    const cliente = montar();
    await waitFor(() => expect(screen.getByText("Cartera total")).toBeInTheDocument());
    expect(cliente.panel).toHaveBeenCalledTimes(1);
  });
});
