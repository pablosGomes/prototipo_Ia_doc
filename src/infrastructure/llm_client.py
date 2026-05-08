import os

from google import genai

MODELO_PADRAO = "gemini-2.0-flash"  # rápido e gratuito no tier free


class LLMError(Exception):
    pass


def gerar_texto(prompt: str, modelo: str = MODELO_PADRAO) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY não configurada — verifique o arquivo .env")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=modelo,
            contents=prompt,
        )
    except Exception as e:
        raise LLMError(f"Erro ao chamar Gemini: {e}") from e

    if not response.text:
        raise LLMError("Gemini retornou resposta vazia")

    return response.text
