"""El prompt del informe. Las métricas son datos, nunca instrucciones del usuario."""

import json


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
