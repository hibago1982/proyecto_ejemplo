/**
 * Botones de exportacion.
 *
 * Nacen de un defecto encontrado en el navegador: eran enlaces `<a href>`, que
 * no llevan cabeceras, asi que el usuario recibia un 401 al pulsarlos.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Cliente } from "../api/cliente";
import { Exportar } from "../componentes/Exportar";

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:falso");
  URL.revokeObjectURL = vi.fn();
});

function montar(descargar: ReturnType<typeof vi.fn>) {
  render(<Exportar cliente={{ descargar } as unknown as Cliente} />);
}

describe("Exportar", () => {
  it("descarga con petición autenticada, no con un enlace", async () => {
    const descargar = vi
      .fn()
      .mockResolvedValue({ blob: new Blob(["x"]), nombre: "cartera.xlsx" });
    montar(descargar);

    await userEvent.click(screen.getByRole("button", { name: "Excel" }));
    await waitFor(() => expect(descargar).toHaveBeenCalledWith("excel", undefined));
    // Un <a href> no puede llevar cabeceras: por eso no hay ninguno aquí.
    expect(document.querySelectorAll("a[href*='exportar']")).toHaveLength(0);
  });

  it("libera el blob para no retener el archivo en memoria", async () => {
    montar(vi.fn().mockResolvedValue({ blob: new Blob(["x"]), nombre: "c.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "PDF" }));
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled());
  });

  it("avisa mientras genera, porque el PDF tarda", async () => {
    let resolver: (v: unknown) => void = () => {};
    const descargar = vi.fn(() => new Promise((r) => { resolver = r; }));
    montar(descargar as unknown as ReturnType<typeof vi.fn>);

    await userEvent.click(screen.getByRole("button", { name: "PDF" }));
    expect(screen.getByText("Generando…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Excel" })).toBeDisabled();

    resolver({ blob: new Blob(["x"]), nombre: "c.pdf" });
    await waitFor(() => expect(screen.getByRole("button", { name: "PDF" })).toBeEnabled());
  });

  it("muestra el error del servidor si falla", async () => {
    montar(vi.fn().mockRejectedValue(new Error("El corte no está calculado.")));
    await userEvent.click(screen.getByRole("button", { name: "Excel" }));
    await waitFor(() =>
      expect(screen.getByText("El corte no está calculado.")).toBeInTheDocument(),
    );
  });
});
