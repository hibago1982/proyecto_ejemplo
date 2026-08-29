/**
 * Lista de gestion y detalle del cliente.
 *
 * Se centran en lo que el gestor necesita para trabajar sin abrir el informe
 * anterior: que cada fila diga por que esta ahi, que los filtros lleguen al
 * API, y que una alerta de cliente no se muestre como si fuera de una factura.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Cliente } from "../api/cliente";
import { DetalleCliente } from "../DetalleCliente";
import { ListaGestion } from "../ListaGestion";
import { DETALLE, LISTA } from "./datos";

function clienteFalso(sobrescribir: Partial<Cliente> = {}): Cliente {
  return {
    cortes: vi.fn().mockResolvedValue([]),
    panel: vi.fn(),
    gestion: vi.fn().mockResolvedValue(LISTA),
    cliente: vi.fn().mockResolvedValue(DETALLE),
    configuracion: vi.fn(),
    ...sobrescribir,
  } as unknown as Cliente;
}

function montar(nodo: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={qc}>{nodo}</QueryClientProvider>);
}

beforeEach(() => {
  window.location.hash = "";
});

describe("Lista de gestión", () => {
  it("muestra las alertas con su acción sugerida", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() => expect(screen.getByText("A07")).toBeInTheDocument());
    expect(screen.getByText("Escalar")).toBeInTheDocument();
    expect(screen.getByText("Revisar comportamiento")).toBeInTheDocument();
  });

  it("los filtros rápidos de §8.2 llegan al API", async () => {
    const cliente = clienteFalso();
    montar(<ListaGestion cliente={cliente} />);
    await waitFor(() => expect(screen.getByText("A07")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Críticas" }));
    await waitFor(() =>
      expect(cliente.gestion).toHaveBeenCalledWith(
        expect.objectContaining({ prioridad_minima: 4 }),
      ),
    );
  });

  it("el filtro de por vencer usa el bucket B00", async () => {
    const cliente = clienteFalso();
    montar(<ListaGestion cliente={cliente} />);
    await waitFor(() => expect(screen.getByText("A07")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Por vencer" }));
    await waitFor(() =>
      expect(cliente.gestion).toHaveBeenCalledWith(
        expect.objectContaining({ bucket: "B00" }),
      ),
    );
  });

  it("la búsqueda viaja al API en vez de filtrarse aquí", async () => {
    const cliente = clienteFalso();
    montar(<ListaGestion cliente={cliente} />);
    await waitFor(() => expect(screen.getByText("A07")).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText("Buscar por NIT o factura"), "3018");
    await waitFor(() =>
      expect(cliente.gestion).toHaveBeenCalledWith(
        expect.objectContaining({ busqueda: "3018" }),
      ),
    );
  });

  it("cambiar el orden vuelve a pedir al API", async () => {
    const cliente = clienteFalso();
    montar(<ListaGestion cliente={cliente} />);
    await waitFor(() => expect(screen.getByText("A07")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText(/Orden/), "saldo");
    await waitFor(() =>
      expect(cliente.gestion).toHaveBeenCalledWith(
        expect.objectContaining({ orden: "saldo" }),
      ),
    );
  });

  it("una alerta de cliente no finge tener factura", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() => expect(screen.getByText("A10")).toBeInTheDocument());
    // La fila de A10 muestra un guion, no una factura inventada.
    const fila = screen.getByText("A10").closest("tr")!;
    expect(fila).toHaveTextContent("—");
  });

  it("cada alerta puede explicar por qué se disparó (§7.4)", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() => expect(screen.getByText("A10")).toBeInTheDocument());

    const botones = screen.getAllByLabelText("Por qué se disparó esta alerta");
    await userEvent.click(botones[2]!);
    expect(
      screen.getByText(/el cliente tiene 4 facturas vencidas/),
    ).toBeInTheDocument();
  });

  it("una búsqueda sin resultados lo dice con las palabras del usuario", async () => {
    const cliente = clienteFalso({
      gestion: vi.fn().mockResolvedValue({ ...LISTA, total: 0, filas: [] }),
    });
    montar(<ListaGestion cliente={cliente} />);
    await waitFor(() =>
      expect(screen.getByText(/No hay alertas con este filtro/)).toBeInTheDocument(),
    );
  });
});

describe("Detalle del cliente", () => {
  it("muestra los indicadores de §6", async () => {
    montar(<DetalleCliente cliente={clienteFalso()} nit="90010001818" />);
    await waitFor(() =>
      expect(screen.getByText("TEXTILES DE ANTIOQUIA SAS")).toBeInTheDocument(),
    );
    for (const etiqueta of [
      "Cartera total",
      "Vencida",
      "Más de 90 días",
      "Factura más antigua",
      "Facturas vencidas",
    ]) {
      expect(screen.getByText(etiqueta)).toBeInTheDocument();
    }
    expect(screen.getByText("4 de 4")).toBeInTheDocument();
  });

  it("explica el marcador de riesgo en vez de mostrar solo su código", async () => {
    montar(<DetalleCliente cliente={clienteFalso()} nit="90010001818" />);
    await waitFor(() => expect(screen.getByText("M04")).toBeInTheDocument());
    expect(
      screen.getByText(/alguna factura pasa de 90 días/),
    ).toBeInTheDocument();
  });

  it("muestra el desglose cuando hubo nota crédito (C-10)", async () => {
    montar(<DetalleCliente cliente={clienteFalso()} nit="90010001818" />);
    await waitFor(() => expect(screen.getByText("A04")).toBeInTheDocument());
    // Sin esto, el saldo no cuadraria con el ERP y nadie sabria por que.
    expect(screen.getByText(/bruto .* − crédito/)).toBeInTheDocument();
  });

  it("dice que el historial de gestiones es de la fase 6", async () => {
    montar(<DetalleCliente cliente={clienteFalso()} nit="90010001818" />);
    await waitFor(() =>
      expect(screen.getByText(/es de la fase 6/)).toBeInTheDocument(),
    );
  });

  it("un cliente inexistente muestra el mensaje del backend", async () => {
    const cliente = clienteFalso({
      cliente: vi
        .fn()
        .mockRejectedValue(new Error("El cliente '000' no tiene cartera en el corte.")),
    });
    montar(<DetalleCliente cliente={cliente} nit="000" />);
    await waitFor(() =>
      expect(screen.getByText(/no tiene cartera en el corte/)).toBeInTheDocument(),
    );
  });
});

describe("Explicación de la alerta", () => {
  it("el clic la deja fijada en vez de cerrarla tras el hover", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() => expect(screen.getByText("A10")).toBeInTheDocument());

    const boton = screen.getAllByLabelText("Por qué se disparó esta alerta")[2]!;
    // userEvent pasa el cursor antes de pulsar, igual que un raton real.
    await userEvent.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");

    await userEvent.unhover(boton);
    expect(
      screen.getByText(/el cliente tiene 4 facturas vencidas/),
    ).toBeInTheDocument();
  });

  it("no arrastra al usuario fuera de la lista al abrirla", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() => expect(screen.getByText("A10")).toBeInTheDocument());

    await userEvent.click(screen.getAllByLabelText("Por qué se disparó esta alerta")[0]!);
    expect(window.location.hash).toBe("");
  });
});

describe("Nombre del cliente en la bandeja", () => {
  it("se muestra el nombre y no solo el NIT", async () => {
    montar(<ListaGestion cliente={clienteFalso()} />);
    await waitFor(() =>
      expect(screen.getAllByText("TEXTILES DE ANTIOQUIA SAS").length).toBeGreaterThan(0),
    );
  });

  it("si el nombre falta, el NIT ocupa su lugar en vez de dejar la celda vacía", async () => {
    const sinNombre = {
      ...LISTA,
      filas: [{ ...LISTA.filas[0]!, cliente_nombre: "" }],
    };
    montar(<ListaGestion cliente={clienteFalso({ gestion: vi.fn().mockResolvedValue(sinNombre) })} />);
    await waitFor(() => expect(screen.getByText("90010001818")).toBeInTheDocument());
  });
});
