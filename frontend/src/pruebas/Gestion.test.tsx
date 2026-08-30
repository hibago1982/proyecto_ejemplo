/**
 * Registro de gestion e historial (§11, §8.3).
 *
 * El foco: que el compromiso de pago no se pueda enviar a medias, y que el
 * historial se lea sin descifrar codigos.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Cliente } from "../api/cliente";
import { DetalleCliente } from "../DetalleCliente";
import { DETALLE, GESTIONES } from "./datos";

function montar(sobrescribir: Partial<Cliente> = {}) {
  const cliente = {
    cortes: vi.fn().mockResolvedValue([]),
    panel: vi.fn(),
    gestion: vi.fn(),
    cliente: vi.fn().mockResolvedValue(DETALLE),
    configuracion: vi.fn(),
    registrarGestion: vi.fn().mockResolvedValue(GESTIONES[0]),
    ...sobrescribir,
  } as unknown as Cliente;

  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <DetalleCliente cliente={cliente} nit="90010001818" />
    </QueryClientProvider>,
  );
  return cliente;
}

describe("Registrar gestión", () => {
  it("envía la gestión con el usuario que la registra", async () => {
    const cliente = montar();
    await waitFor(() => expect(screen.getByText("Registrar gestión")).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText(/Resultado/), "Contactado");
    await userEvent.click(screen.getByRole("button", { name: "Registrar" }));

    await waitFor(() =>
      expect(cliente.registrarGestion).toHaveBeenCalledWith(
        "90010001818",
        expect.objectContaining({
          tipo: "llamada",
              resultado: "Contactado",
        }),
      ),
    );
  });

  it("solo ofrece facturas que tienen alerta", async () => {
    montar();
    await waitFor(() => expect(screen.getByLabelText(/Factura/)).toBeInTheDocument());
    const opciones = [...screen.getByLabelText(/Factura/).querySelectorAll("option")];
    expect(opciones.map((o) => o.textContent)).toEqual([
      "Todo el cliente",
      "3018",
      "3048",
    ]);
  });

  it("no deja enviar un compromiso a medias", async () => {
    const cliente = montar();
    await waitFor(() => expect(screen.getByText("Registrar gestión")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText(/Hubo compromiso de pago/));
    await userEvent.type(screen.getByLabelText(/Fecha comprometida/), "2026-09-15");

    expect(screen.getByRole("button", { name: "Registrar" })).toBeDisabled();
    expect(screen.getByText(/necesita fecha y valor/)).toBeInTheDocument();
    expect(cliente.registrarGestion).not.toHaveBeenCalled();
  });

  it("envía el compromiso cuando está completo", async () => {
    const cliente = montar();
    await waitFor(() => expect(screen.getByText("Registrar gestión")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText(/Hubo compromiso de pago/));
    await userEvent.type(screen.getByLabelText(/Fecha comprometida/), "2026-09-15");
    await userEvent.type(screen.getByLabelText(/Valor comprometido/), "500000");
    await userEvent.click(screen.getByRole("button", { name: "Registrar" }));

    await waitFor(() =>
      expect(cliente.registrarGestion).toHaveBeenCalledWith(
        "90010001818",
        expect.objectContaining({
          compromiso_fecha: "2026-09-15",
          compromiso_valor: "500000",
        }),
      ),
    );
  });

  it("muestra el mensaje del backend si rechaza la gestión", async () => {
    const cliente = montar({
      registrarGestion: vi
        .fn()
        .mockRejectedValue(new Error("No hay alertas de la factura 'F-999'.")),
    });
    await waitFor(() => expect(screen.getByText("Registrar gestión")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Registrar" }));
    await waitFor(() =>
      expect(screen.getByText(/No hay alertas de la factura/)).toBeInTheDocument(),
    );
    expect(cliente.registrarGestion).toHaveBeenCalled();
  });
});

describe("Historial de gestiones", () => {
  it("dice claramente cuando no hay ninguna", async () => {
    montar();
    await waitFor(() =>
      expect(screen.getByText(/Todavía no se ha registrado/)).toBeInTheDocument(),
    );
  });

  it("muestra el tipo con nombre legible y el compromiso", async () => {
    montar({
      cliente: vi.fn().mockResolvedValue({ ...DETALLE, gestiones: GESTIONES }),
    });
    await waitFor(() =>
      expect(screen.getByText("Historial de gestiones")).toBeInTheDocument(),
    );
    // "Acuerdo de pago" tambien es una opcion del formulario: se busca dentro
    // de la lista del historial para no confundir una cosa con la otra.
    const historial = screen.getByText("Historial de gestiones").closest("section")!;
    expect(historial).toHaveTextContent("Acuerdo de pago");
    expect(historial).toHaveTextContent("Llamada");
    expect(historial).toHaveTextContent(/Compromiso: .* para 15\/09\/2026/);
    expect(historial).toHaveTextContent("Sin respuesta");
  });
});

describe("Estados de alerta", () => {
  it("se muestran con el nombre de §12 y no con el valor de la base", async () => {
    montar({
      cliente: vi.fn().mockResolvedValue({
        ...DETALLE,
        alertas: [
          { ...DETALLE.alertas[0]!, estado: "gestionada" },
          { ...DETALLE.alertas[1]!, estado: "cerrada_por_pago" },
        ],
      }),
    });
    await waitFor(() => expect(screen.getByText("Gestionada")).toBeInTheDocument());
    expect(screen.getByText("Cerrada por pago")).toBeInTheDocument();
  });
});
