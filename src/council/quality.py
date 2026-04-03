"""
Quality pipeline: behavior presets, critic pass, LLM-based agent weights for synthesis.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import AgentResponse
from src.agents.core_agents import Synthesizer
from src.llm_providers import LLMProvider


def preset_instructions(preset: str) -> str:
    """Extra instructions appended to the user query for all agents."""
    p = (preset or "default").strip().lower()
    if p == "short":
        return (
            "\n\n[Tryb: KRÓTKO] Odpowiedz zwięźle: maksymalnie 8–10 zdań łącznie, "
            "bez powtórzeń; najważniejsze punkty w listach."
        )
    if p == "with_sources":
        return (
            "\n\n[Tryb: ŹRÓDŁA] Gdy korzystasz z załączonego kontekstu z bazy wiedzy, "
            "wskaż przy kluczowych twierdzeniach skąd to pochodzi (tytuł / fragment). "
            "Nie wymyślaj źródeł spoza kontekstu."
        )
    if p == "kb_only":
        return (
            "\n\n[Tryb: TYLKO BAZA WIEDZY] Odpowiadaj wyłącznie na podstawie dostarczonego "
            "kontekstu z bazy wiedzy. Jeśli kontekstu brak lub jest niewystarczający, "
            "jasno napisz że nie ma danych w bazie — nie uzupełniaj wiedzą ogólną."
        )
    return ""


def preset_synthesis_instructions(preset: str) -> str:
    p = (preset or "default").strip().lower()
    if p == "short":
        return "Synteza musi być bardzo zwięzła (do ~12 zdań)."
    if p == "with_sources":
        return (
            "W syntezie przy każdej kluczowej tezie podaj odniesienie do perspektyw agentów "
            "lub do cytowanego kontekstu (bez zmyślonych odnośników)."
        )
    if p == "kb_only":
        return (
            "Syntetyzuj wyłącznie to, co wynika z kontekstu KB i odpowiedzi agentów opartych na KB. "
            "Nie dodawaj faktów spoza dostarczonych materiałów."
        )
    return ""


async def critic_review(
    llm: LLMProvider,
    query: str,
    context: List[str],
    responses: List[AgentResponse],
) -> Tuple[str, int, int]:
    """Returns (critic_markdown, prompt_tokens, completion_tokens)."""
    ctx = "\n\n".join(context[:20]) if context else "(brak kontekstu KB)"
    parts = []
    for r in responses:
        parts.append(f"### {r.agent_name}\n{r.content}\n")
    block = "\n".join(parts)
    system = """Jesteś redaktorem i krytykiem merytorycznym. Wskaż:
1) ewentualne sprzeczności między odpowiedziami,
2) luki lub ryzyko halucynacji,
3) co powinno wejść do syntezy końcowej.
Odpowiedz po polsku, zwięźle (markdown)."""
    user = f"Pytanie użytkownika:\n{query}\n\nKontekst KB:\n{ctx}\n\nOdpowiedzi agentów:\n{block}"
    out = await llm.generate(system_prompt=system, user_prompt=user, temperature=0.3)
    return out.content, out.prompt_tokens, out.completion_tokens


async def llm_agent_weights(
    llm: LLMProvider,
    query: str,
    responses: List[AgentResponse],
) -> Tuple[List[float], int, int]:
    """Assigns non-negative weights summing ~1 for each agent response."""
    lines = [f"- {r.agent_name}: {r.content[:1200]}" for r in responses]
    system = """Ocen przydatność każdej odpowiedzi względem pytania użytkownika.
Zwróć WYŁĄCZNIE JSON: {"weights": [ ... ]} — jedna liczba nieujemna na agenta w tej samej kolejności co lista.
Nie dodawaj tekstu poza JSON."""
    user = f"Pytanie: {query}\n\nOdpowiedzi (w kolejności):\n" + "\n".join(lines)
    out = await llm.generate(system_prompt=system, user_prompt=user, temperature=0.2)
    raw = out.content.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        raw = m.group(0)
    try:
        data = json.loads(raw)
        w = data.get("weights")
        if not isinstance(w, list) or len(w) != len(responses):
            raise ValueError("bad shape")
        weights = [max(0.0, float(x)) for x in w]
        s = sum(weights) or 1.0
        weights = [x / s for x in weights]
    except (json.JSONDecodeError, ValueError, TypeError):
        n = len(responses)
        weights = [1.0 / n] * n if n else []
    return weights, out.prompt_tokens, out.completion_tokens


async def synthesize_with_critic_and_weights(
    synthesizer: Synthesizer,
    query: str,
    context: List[str],
    responses: List[AgentResponse],
    *,
    critic_text: Optional[str],
    weights: Optional[List[float]],
    preset: str,
) -> AgentResponse:
    """Builds augmented user prompt and calls synthesizer.synthesize."""
    base = synthesizer.build_user_prompt(query, context, responses)
    extras: List[str] = []
    syn_inst = preset_synthesis_instructions(preset)
    if syn_inst:
        extras.append(f"## Instrukcje stylu syntezy\n{syn_inst}")
    if critic_text:
        extras.append(f"## Uwagi redaktora (uwzględnij przy syntezie)\n{critic_text}")
    if weights and len(weights) == len(responses):
        w_lines = [f"- {responses[i].agent_name}: waga {weights[i]:.3f}" for i in range(len(responses))]
        extras.append(
            "## Wagi istotności odpowiedzi\n"
            + "\n".join(w_lines)
            + "\n(Ważniejsze perspektywy powinny mocniej wpływać na syntezę.)"
        )
    if extras:
        user_prompt = base + "\n\n" + "\n\n".join(extras)
    else:
        user_prompt = base

    system_prompt = synthesizer.get_system_prompt()
    llm_response = await synthesizer.provider.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.45,
    )
    return AgentResponse(
        agent_name=f"{synthesizer.emoji} {synthesizer.name}",
        role=synthesizer.role,
        perspective=synthesizer.config.personality,
        content=llm_response.content,
        provider_used=synthesizer.provider.get_name(),
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        total_tokens=llm_response.total_tokens,
        model=llm_response.model,
    )
