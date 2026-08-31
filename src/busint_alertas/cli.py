"""Administracion por linea de comandos.

Lo minimo para poner en marcha un despliegue y operarlo sin abrir una consola de
base de datos: crear la primera empresa, sus usuarios y disparar un corte.

    python -m busint_alertas.cli sembrar E01
    python -m busint_alertas.cli usuario crear admin E01 administrador
    python -m busint_alertas.cli umbral E01 R01 umbral_saldo_alto 5000000 --usuario admin
    python -m busint_alertas.cli ejecutar E01 --corte 2026-08-21
    python -m busint_alertas.cli estado E01
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import date
from decimal import Decimal

from .fuentes.base import ErrorDeOrigen
from .fuentes.entorno import construir_fuente
from .core.fechas import hoy
from .core.tipos import Rol
from .ejecucion import ejecutar_corte
from .persistencia import (
    RepositorioCartera, cargar, crear_engine, fabrica_de_sesiones,
    fijar_parametro, sembrar,
)
from .persistencia.usuarios import crear as crear_usuario

ROLES = {r.name.lower(): r for r in Rol}


def sesiones():
    url = os.environ.get("BUSINT_DB_URL")
    if not url:
        sys.exit("Falta BUSINT_DB_URL.")
    return fabrica_de_sesiones(crear_engine(url, pool_pre_ping=True))


def cmd_sembrar(args) -> int:
    """Deja la empresa con los buckets de §5.2 y sus reglas declaradas.

    No asigna umbrales monetarios: §16 prohibe deducirlos de una base de
    demostracion, asi que R01 y R02 nacen inactivas a proposito.
    """
    with sesiones()() as s:
        sembrar(
            s, args.empresa,
            dias_preventivos=args.dias_preventivos,
            n_facturas_vencidas=args.n_facturas_vencidas,
            pct_mayor_90_umbral=Decimal(args.pct_mayor_90),
        )
        s.commit()
        config = cargar(s, args.empresa)
    print(f"Empresa {args.empresa} sembrada: {len(config.buckets)} buckets.")
    print("R01 y R02 quedan inactivas hasta que asignes sus umbrales:")
    print(f"  python -m busint_alertas.cli umbral {args.empresa} R01 umbral_saldo_alto <valor>")
    return 0


def cmd_usuario_crear(args) -> int:
    rol = ROLES.get(args.rol.lower())
    if rol is None:
        sys.exit(f"Rol '{args.rol}' no valido. Usa: {', '.join(ROLES)}.")

    clave = os.environ.get("BUSINT_CLAVE_USUARIO") or getpass.getpass("Clave: ")
    if len(clave) < 8:
        sys.exit("La clave debe tener al menos 8 caracteres.")

    with sesiones()() as s:
        try:
            crear_usuario(s, args.usuario, clave, args.empresa, rol, args.nombre or "")
        except ValueError as e:
            sys.exit(str(e))
        s.commit()
    print(f"Usuario '{args.usuario}' creado en {args.empresa} como {rol.etiqueta}.")
    return 0


def cmd_umbral(args) -> int:
    with sesiones()() as s:
        try:
            fijar_parametro(s, args.empresa, args.regla, args.parametro,
                            args.valor, args.usuario)
        except LookupError as e:
            sys.exit(str(e))
        s.commit()
    print(f"{args.regla}.{args.parametro} = {args.valor} (por {args.usuario}).")
    return 0


def cmd_ejecutar(args) -> int:
    corte = date.fromisoformat(args.corte) if args.corte else hoy()
    fuente = construir_fuente()
    try:
        with sesiones()() as s:
            corrida = ejecutar_corte(s, fuente, args.empresa, corte)
            s.commit()
    except ErrorDeOrigen as e:
        # El origen no dio los datos. Es una condicion esperada y accionable
        # (archivo de otro corte, ERP caido, columnas cambiadas), no un fallo
        # del programa: un traceback aqui solo hace pensar que se rompio algo.
        sys.exit(f"No se pudieron leer los datos: {e}")
    except LookupError as e:
        sys.exit(str(e))
    r = corrida.resumen
    print(
        f"Corte {corte} de {args.empresa}: {corrida.filas_leidas} filas leidas, "
        f"{r.alertas_insertadas} alertas nuevas, {r.alertas_actualizadas} "
        f"actualizadas, {r.alertas_cerradas} cerradas, {r.clientes} clientes."
    )
    if corrida.resultado.reglas_inactivas:
        print("Reglas sin evaluar:")
        for codigo, motivo in corrida.resultado.reglas_inactivas.items():
            print(f"  {codigo}: {motivo}")
    return 0


def cmd_estado(args) -> int:
    with sesiones()() as s:
        repo = RepositorioCartera(s)
        cortes = repo.cortes_disponibles(args.empresa)
        if not cortes:
            print(f"{args.empresa} no tiene ningun corte calculado.")
            return 0
        ultimo = cortes[0]
        alertas = repo.alertas_del_corte(args.empresa, ultimo)
        riesgo = repo.riesgo_del_corte(args.empresa, ultimo)
        total = sum(c.cartera_total for c in riesgo)
    print(f"Empresa {args.empresa}")
    print(f"  cortes calculados : {len(cortes)} (ultimo {ultimo})")
    print(f"  clientes          : {len(riesgo)}")
    print(f"  alertas activas   : {len(alertas)}")
    print(f"  cartera total     : {total:,.2f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="busint_alertas.cli", description="Administracion del motor de alertas."
    )
    sub = p.add_subparsers(dest="orden", required=True)

    s1 = sub.add_parser("sembrar", help="Crear buckets y reglas de una empresa")
    s1.add_argument("empresa")
    s1.add_argument("--dias-preventivos", type=int, default=15)
    s1.add_argument("--n-facturas-vencidas", type=int, default=3)
    s1.add_argument("--pct-mayor-90", default="40")
    s1.set_defaults(func=cmd_sembrar)

    s2 = sub.add_parser("usuario", help="Gestion de usuarios")
    sub2 = s2.add_subparsers(dest="accion", required=True)
    s2c = sub2.add_parser("crear")
    s2c.add_argument("usuario")
    s2c.add_argument("empresa")
    s2c.add_argument("rol", choices=sorted(ROLES))
    s2c.add_argument("--nombre", default="")
    s2c.set_defaults(func=cmd_usuario_crear)

    s3 = sub.add_parser("umbral", help="Fijar el umbral de una regla")
    s3.add_argument("empresa")
    s3.add_argument("regla")
    s3.add_argument("parametro")
    s3.add_argument("valor")
    s3.add_argument("--usuario", default="cli")
    s3.set_defaults(func=cmd_umbral)

    s4 = sub.add_parser("ejecutar", help="Correr el motor para un corte")
    s4.add_argument("empresa")
    s4.add_argument("--corte", help="AAAA-MM-DD. Por defecto, hoy en Bogota.")
    s4.set_defaults(func=cmd_ejecutar)

    s5 = sub.add_parser("estado", help="Resumen del ultimo corte")
    s5.add_argument("empresa")
    s5.set_defaults(func=cmd_estado)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
