"""Adaptador de Groq. La salida se valida y, si no es JSON, se reintenta."""

import json

import httpx

from app.domain.entities.report import ReportContent
from app.domain.errors import ExternalServiceError
from app.infrastructure.ai.tutor import ReportDraft

MAX_ATTEMPTS = 2
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_SECONDS = 30.0


class GroqTutor:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def advise(self, prompt: str) -> ReportContent:
        if not self._api_key.strip():
            raise ExternalServiceError("Falta GROQ_API_KEY.")
        last_error = "sin respuesta"
        for _ in range(MAX_ATTEMPTS):
            raw = await self._complete(prompt)
            try:
                return ReportDraft.model_validate(json.loads(_json_text(raw))).to_content()
            except (json.JSONDecodeError, ValueError) as error:
                last_error = str(error)
        raise ExternalServiceError(f"Groq no devolvió un informe válido: {last_error}")

    async def _complete(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise ExternalServiceError("Groq no respondió.") from error
        return _message_text(response.json())


def _json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if text.endswith("```"):
            text = text[: -len("```")].strip()
    return text


def _message_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ExternalServiceError("Groq devolvió una respuesta vacía.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ExternalServiceError("Groq devolvió una respuesta vacía.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ExternalServiceError("Groq devolvió una respuesta vacía.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ExternalServiceError("Groq devolvió una respuesta vacía.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ExternalServiceError("Groq devolvió una respuesta vacía.")
    return content
