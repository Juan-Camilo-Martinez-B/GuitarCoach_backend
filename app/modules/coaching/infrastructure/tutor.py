"""La forma de la respuesta del modelo. El modelo concreto queda detrás del adaptador."""

from pydantic import BaseModel, Field

from app.modules.coaching.domain.report import ReportContent


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
