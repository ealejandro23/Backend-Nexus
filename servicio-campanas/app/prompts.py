"""Construcción de prompts para el worker del LLM."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """Eres el redactor de campañas de Nexo Retail.
Escribes en español de Chile, con un tono {tono}.
Reglas obligatorias:
1. No inventes datos, precios, stock ni plazos.
2. No incluyas datos personales: no nombres, correos, teléfonos, RUT,
   direcciones, comunas ni regiones.
3. Usa sólo las categorías y señales entregadas.
4. Si no hay recomendaciones, invita a descubrir el catálogo sin inventar.
5. Devuelve EXCLUSIVAMENTE un JSON válido con las claves "asunto" y "mensaje".
   - "asunto": máximo 70 caracteres.
   - "mensaje": entre 2 y 5 frases, máximo 700 caracteres.
"""

USER_TEMPLATE = """Genera una campaña de {canal} para un cliente.
Perfil anonimizado:
{perfil}

Recomendaciones (categoría, propensión):
{recomendaciones}

{instruccion_descuento}
"""


def _json_compacto(valor: Any, max_chars: int) -> str:
    texto = json.dumps(valor, ensure_ascii=False, default=str)
    if len(texto) > max_chars:
        texto = texto[:max_chars] + "..."
    return texto


def construir_prompt(
    perfil_anonimizado: dict[str, Any],
    recomendaciones: list[dict[str, Any]],
    canal: str,
    tono: str,
    incluir_descuento: bool = False,
) -> tuple[str, str]:
    """Devuelve (system_prompt, user_prompt) listos para NVIDIA."""
    instruccion_descuento = (
        "Puedes mencionar un beneficio genérico de bienvenida, sin inventar el monto."
        if incluir_descuento
        else "No menciones descuentos ni promociones."
    )
    user = USER_TEMPLATE.format(
        canal=canal,
        perfil=_json_compacto(perfil_anonimizado, 2500),
        recomendaciones=_json_compacto(recomendaciones[:5], 2500),
        instruccion_descuento=instruccion_descuento,
    )
    return SYSTEM_PROMPT.format(tono=tono), user
