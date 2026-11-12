"""Anonimización de datos antes de enviar cualquier contenido al LLM.

Regla de oro: al proveedor del LLM sólo viajan datos agregados y un
identificador seudonimizado. Nunca se envían nombres, correos, teléfonos,
RUT, direcciones, comuna ni región.

La seudonimización usa SHA-256 con una sal configurable. El mismo usuario
produce siempre el mismo hash dentro de una instalación, pero el hash no
permite recuperar el identificador original.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Claves que jamás deben llegar al LLM.
PII_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "usuario_id",
        "user_id",
        "nombre",
        "nombres",
        "apellido",
        "apellidos",
        "nombre_completo",
        "email",
        "correo",
        "correo_electronico",
        "e_mail",
        "telefono",
        "teléfono",
        "fono",
        "celular",
        "movil",
        "móvil",
        "direccion",
        "dirección",
        "domicilio",
        "rut",
        "dni",
        "pasaporte",
        "comuna",
        "region",
        "región",
        "ciudad",
        "fecha_nacimiento",
        "tarjeta",
        "password",
        "contrasena",
        "contraseña",
        "ip",
    }
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_RUT_RE = re.compile(r"(?<!\d)\d{1,2}\.?\d{3}\.?\d{3}-[\dkK](?!\w)")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?56[\s\-]?)?(?:9[\s\-]?\d{4}[\s\-]?\d{4}|2[\s\-]?\d{4}[\s\-]?\d{4})(?!\d)"
)
_ADDRESS_RE = re.compile(
    r"\b(?:av\.?|avenida|calle|pasaje|camino|villa|poblaci[oó]n)\s+[^,;.\n]{3,80}",
    re.IGNORECASE,
)

_TOKEN_EMAIL = "<EMAIL>"
_TOKEN_RUT = "<RUT>"
_TOKEN_PHONE = "<TELEFONO>"
_TOKEN_ADDRESS = "<DIRECCION>"


def hash_usuario(usuario_id: str | None, salt: str) -> str:
    """Devuelve un seudónimo estable y no reversible para el usuario."""
    if not usuario_id:
        return "u_anonimo"
    digest = hashlib.sha256(f"{salt}:{usuario_id}".encode("utf-8")).hexdigest()
    return f"u_{digest[:16]}"


def anonimizar_texto(texto: str) -> str:
    """Reemplaza PII detectable dentro de un texto libre."""
    if not texto:
        return texto
    limpio = _EMAIL_RE.sub(_TOKEN_EMAIL, texto)
    limpio = _RUT_RE.sub(_TOKEN_RUT, limpio)
    limpio = _PHONE_RE.sub(_TOKEN_PHONE, limpio)
    limpio = _ADDRESS_RE.sub(_TOKEN_ADDRESS, limpio)
    return limpio


def _bucket_edad(edad: Any) -> str:
    """Convierte la edad exacta en un rango (dato menos identificable)."""
    try:
        valor = int(edad)
    except (TypeError, ValueError):
        return "no_disponible"
    if valor < 18:
        return "<18"
    if valor < 25:
        return "18-24"
    if valor < 35:
        return "25-34"
    if valor < 45:
        return "35-44"
    if valor < 55:
        return "45-54"
    if valor < 65:
        return "55-64"
    return "65+"


def _limpiar_valor(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {
            clave: _limpiar_valor(subvalor)
            for clave, subvalor in valor.items()
            if str(clave).lower() not in PII_KEYS
        }
    if isinstance(valor, (list, tuple, set)):
        return [_limpiar_valor(item) for item in valor]
    if isinstance(valor, str):
        return anonimizar_texto(valor)
    return valor


def anonimizar_perfil(perfil: dict[str, Any], salt: str) -> dict[str, Any]:
    """Construye el perfil mínimo que se enviará al LLM.

    - Elimina claves PII de forma recursiva.
    - Convierte la edad exacta en rango etario.
    - Agrega un seudónimo estable del usuario.
    - Conserva sólo variables de comportamiento útiles para el copy.
    """
    usuario_id = perfil.get("usuario_id") or perfil.get("user_id") or perfil.get("id")
    limpio = _limpiar_valor(
        {clave: valor for clave, valor in perfil.items() if str(clave).lower() not in PII_KEYS}
    )

    if "edad" in perfil:
        limpio["rango_edad"] = _bucket_edad(perfil.get("edad"))
        limpio.pop("edad", None)

    limpio["usuario_hash"] = hash_usuario(str(usuario_id) if usuario_id else None, salt)

    # Sólo dejamos variables con valor de negocio; el resto se descarta.
    permitidas = {
        "usuario_hash",
        "rango_edad",
        "acepta_marketing",
        "frecuencia_compra",
        "ticket_promedio",
        "categorias",
        "compras_previas",
        "ultima_compra_dias",
        "canal_preferido",
        "total_gastado",
    }
    return {clave: valor for clave, valor in limpio.items() if clave in permitidas}
