/**
 * Inicio de sesion (§8.4).
 *
 * Lo que importa aqui: que el error del servidor se muestre tal cual (no
 * distingue usuario de clave a proposito) y que la sesion no se guarde si el
 * servidor la rechaza.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Cliente, Sesion } from "../api/cliente";
import { Entrar } from "../Entrar";

const SESION: Sesion = {
  token: "abc.def",
  expira: "2026-08-31T00:00:00",
  usuario_id: "hbarrera",
  empresa_id: "E01",
  rol: 3,
  rol_etiqueta: "Administrador",
  nombre: "Hiram Barrera",
};

function montar(entrar: ReturnType<typeof vi.fn>) {
  const onEntrar = vi.fn();
  render(
    <Entrar cliente={{ entrar } as unknown as Cliente} onEntrar={onEntrar} />,
  );
  return onEntrar;
}

describe("Entrar", () => {
  it("no deja enviar sin usuario y clave", () => {
    montar(vi.fn());
    expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
  });

  it("entrega la sesión cuando las credenciales valen", async () => {
    const entrar = vi.fn().mockResolvedValue(SESION);
    const onEntrar = montar(entrar);

    await userEvent.type(screen.getByLabelText("Usuario"), "hbarrera");
    await userEvent.type(screen.getByLabelText("Clave"), "secreta");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => expect(entrar).toHaveBeenCalledWith("hbarrera", "secreta"));
    expect(onEntrar).toHaveBeenCalledWith(SESION);
  });

  it("muestra el mensaje del servidor y no guarda sesión si falla", async () => {
    const entrar = vi.fn().mockRejectedValue(new Error("Usuario o clave incorrectos."));
    const onEntrar = montar(entrar);

    await userEvent.type(screen.getByLabelText("Usuario"), "hbarrera");
    await userEvent.type(screen.getByLabelText("Clave"), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(screen.getByText("Usuario o clave incorrectos.")).toBeInTheDocument(),
    );
    expect(onEntrar).not.toHaveBeenCalled();
  });

  it("la clave no se muestra en pantalla", async () => {
    montar(vi.fn());
    expect(screen.getByLabelText("Clave")).toHaveAttribute("type", "password");
  });
});
