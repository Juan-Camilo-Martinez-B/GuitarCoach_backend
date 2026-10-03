"""Contrato del tutor y el prompt. El modelo concreto queda detrás del adaptador."""

import json
from typing import Protocol

from pydantic import BaseModel, Field

from app.domain.entities.report import ReportContent


class Tutor(Protocol):
    async def advise(self, prompt: str) -> ReportContent: ...


class PromptBuilder:
    """Arma el prompt. Las métricas son datos, nunca instrucciones del usuario."""

    def build(
        self,
        song_title: str,
        level: str,
        accuracy: float,
        avg_delta_ms: float,
        weak_chords: tuple[str, ...],
    ) -> str:
        metrics = {
            "cancion": song_title,
            "nivel": level,
            "precision": accuracy,
            "desfase_medio_ms": avg_delta_ms,
            "acordes_debiles": list(weak_chords),
        }
        return (
            "Eres profesor de guitarra. Interpreta solo estas métricas calculadas por el sistema. "
            "No inventes cifras. Responde un JSON con diagnostico, ejercicios, plan_semanal y "
            "consejos_tecnica. Cada lista lleva frases concretas.\n"
            f"METRICAS:\n{json.dumps(metrics, ensure_ascii=False)}"
        )


class ReportDraft(BaseModel):
    diagnostico: str = Field(min_length=1)
    ejercicios: list[str] = Field(min_length=1)
    plan_semanal: list[str] = Field(min_length=1)
    consejos_tecnica: list[str] = Field(min_length=1)

    def to_content(self) -> ReportContent:
        return ReportContent(
            diagnostico=self.diagnostico,
            ejercicios=tuple(self.ejercicios),
            plan_semanal=tuple(self.plan_semanal),
            consejos_tecnica=tuple(self.consejos_tecnica),
        )
