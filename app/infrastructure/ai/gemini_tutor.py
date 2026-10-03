"""Adaptador de Gemini. La salida se valida y, si no es JSON, se reintenta."""

import asyncio
import json

from app.domain.entities.report import ReportContent
from app.domain.errors import ExternalServiceError
from app.infrastructure.ai.tutor import ReportDraft

MAX_ATTEMPTS = 2


class GeminiTutor:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def advise(self, prompt: str) -> ReportContent:
        if not self._api_key:
            raise ExternalServiceError("Falta GEMINI_API_KEY.")
        last_error = "sin respuesta"
        for _ in range(MAX_ATTEMPTS):
            raw = await asyncio.to_thread(self._generate, prompt)
            try:
                return ReportDraft.model_validate(json.loads(raw)).to_content()
            except (json.JSONDecodeError, ValueError) as error:
                last_error = str(error)
        raise ExternalServiceError(f"Gemini no devolvió un informe válido: {last_error}")

    def _generate(self, prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(model=self._model, contents=prompt)
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ExternalServiceError("Gemini devolvió una respuesta vacía.")
        return text
