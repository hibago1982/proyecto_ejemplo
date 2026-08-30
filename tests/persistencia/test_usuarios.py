"""Usuarios, claves y roles (§8.4, C-13).

Estas pruebas corren con el coste real de PBKDF2, no con el reducido de las
pruebas del API: verificar el cifrado con un coste falseado no demostraria nada.
"""

from __future__ import annotations

import pytest

from busint_alertas.core.tipos import Rol
from busint_alertas.persistencia.usuarios import (
    ErrorDeAutenticacion,
    autenticar,
    cifrar,
    crear,
    verificar,
)


class TestClaves:
    def test_la_clave_no_se_guarda_en_claro(self):
        cifrada = cifrar("secreta")
        assert "secreta" not in cifrada
        assert cifrada.startswith("pbkdf2_sha256$")

    def test_dos_claves_iguales_dan_hashes_distintos(self):
        """Sal por usuario: sin ella, dos usuarios con la misma clave se
        delatan mutuamente y una tabla precalculada las rompe a las dos."""
        assert cifrar("secreta") != cifrar("secreta")

    def test_verifica_la_correcta_y_rechaza_las_demas(self):
        cifrada = cifrar("secreta")
        assert verificar("secreta", cifrada)
        assert not verificar("Secreta", cifrada)
        assert not verificar("", cifrada)

    def test_un_hash_corrupto_no_revienta(self):
        assert not verificar("secreta", "esto-no-es-un-hash")

    def test_el_coste_viaja_dentro_del_hash(self):
        """Permite subir las iteraciones sin invalidar las claves existentes."""
        assert cifrar("x").split("$")[1] == "480000"


class TestAutenticacion:
    def test_devuelve_la_identidad(self, sesion):
        crear(sesion, "ana", "clave-larga", "E01", Rol.GESTOR, "Ana Restrepo")
        identidad = autenticar(sesion, "ana", "clave-larga")
        assert identidad.empresa_id == "E01"
        assert identidad.rol is Rol.GESTOR

    def test_registra_el_ultimo_acceso(self, sesion):
        fila = crear(sesion, "ana", "clave-larga", "E01", Rol.CONSULTA)
        assert fila.ultimo_acceso is None
        autenticar(sesion, "ana", "clave-larga")
        assert fila.ultimo_acceso is not None

    def test_un_usuario_inactivo_no_entra(self, sesion):
        fila = crear(sesion, "ana", "clave-larga", "E01", Rol.CONSULTA)
        fila.activo = False
        with pytest.raises(ErrorDeAutenticacion):
            autenticar(sesion, "ana", "clave-larga")

    def test_el_mensaje_no_distingue_los_casos(self, sesion):
        """Distinguirlos permitiria averiguar que usuarios existen."""
        crear(sesion, "ana", "clave-larga", "E01", Rol.CONSULTA)
        with pytest.raises(ErrorDeAutenticacion) as sin_usuario:
            autenticar(sesion, "fantasma", "x")
        with pytest.raises(ErrorDeAutenticacion) as mala_clave:
            autenticar(sesion, "ana", "incorrecta")
        assert str(sin_usuario.value) == str(mala_clave.value)

    def test_no_se_repiten_los_nombres_de_usuario(self, sesion):
        crear(sesion, "ana", "clave-larga", "E01", Rol.CONSULTA)
        with pytest.raises(ValueError, match="ya existe"):
            crear(sesion, "ana", "otra-clave", "E02", Rol.ADMINISTRADOR)


class TestRoles:
    def test_los_permisos_son_acumulativos(self):
        assert Rol.ADMINISTRADOR.alcanza(Rol.CONSULTA)
        assert Rol.COORDINADOR.alcanza(Rol.GESTOR)
        assert not Rol.GESTOR.alcanza(Rol.COORDINADOR)
        assert not Rol.CONSULTA.alcanza(Rol.GESTOR)

    def test_cada_rol_tiene_etiqueta_legible(self):
        assert Rol.GESTOR.etiqueta == "Gestor de cartera"
        assert Rol.ADMINISTRADOR.etiqueta == "Administrador"
