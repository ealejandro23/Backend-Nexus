"""Prueba 5: la anonimización elimina PII antes de llamar al LLM."""

from __future__ import annotations

import json

from app.anonymizer import anonimizar_perfil, anonimizar_texto, hash_usuario
from app.prompts import construir_prompt


PERFIL_CON_PII = {
    "usuario_id": "U100000",
    "nombre": "Esteban",
    "apellido": "Gamboa",
    "email": "esteban.gamboa@example.com",
    "telefono": "+56 9 1234 5678",
    "rut": "12.345.678-9",
    "direccion": "Av. Siempre Viva 742",
    "comuna": "Providencia",
    "region": "Metropolitana",
    "edad": 34,
    "acepta_marketing": 1,
    "frecuencia_compra": 4,
    "ticket_promedio": 45000.0,
    "categorias": ["audio", "video"],
    "email_valido": True,
}


def test_anonimizacion_elimina_pii_del_perfil() -> None:
    anonimo = anonimizar_perfil(PERFIL_CON_PII, "salt-de-prueba")
    serializado = json.dumps(anonimo, ensure_ascii=False)

    for valor in (
        "Esteban",
        "Gamboa",
        "esteban.gamboa@example.com",
        "+56 9 1234 5678",
        "12.345.678-9",
        "Av. Siempre Viva 742",
        "Providencia",
        "Metropolitana",
        "U100000",
    ):
        assert valor not in serializado, f"Se filtró PII: {valor}"

    assert anonimo["usuario_hash"].startswith("u_")
    assert anonimo["rango_edad"] == "25-34"
    assert anonimo["categorias"] == ["audio", "video"]
    assert anonimo["acepta_marketing"] == 1
    assert "edad" not in anonimo


def test_hash_es_estable_y_depende_de_la_sal() -> None:
    primero = hash_usuario("U100000", "sal-a")
    segundo = hash_usuario("U100000", "sal-a")
    tercero = hash_usuario("U100000", "sal-b")

    assert primero == segundo
    assert primero != tercero
    assert primero.startswith("u_")
    assert len(primero) == 18


def test_anonimizacion_limpia_texto_libre() -> None:
    texto = (
        "Contactar a Esteban al +56 9 8765 4321 o esteban@example.com, "
        "RUT 11.111.111-1, Av. Los Leones 123."
    )
    limpio = anonimizar_texto(texto)

    assert "esteban@example.com" not in limpio
    assert "8765" not in limpio
    assert "11.111.111-1" not in limpio
    assert "Los Leones" not in limpio
    assert "<EMAIL>" in limpio
    assert "<TELEFONO>" in limpio
    assert "<RUT>" in limpio


def test_prompt_no_contiene_pii() -> None:
    anonimo = anonimizar_perfil(PERFIL_CON_PII, "salt-de-prueba")
    recomendaciones = [{"categoria": "audio", "propension": 0.82}]
    system_prompt, user_prompt = construir_prompt(
        anonimo,
        recomendaciones,
        canal="email",
        tono="cercano",
        incluir_descuento=False,
    )
    completo = system_prompt + user_prompt

    assert "esteban.gamboa@example.com" not in completo
    assert "12.345.678-9" not in completo
    assert "Providencia" not in completo
    assert "audio" in completo
