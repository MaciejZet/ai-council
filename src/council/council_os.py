from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.council.council_os_models import ExpertMemo, KnowledgeStatus, extract_json_object
from src.council.expert_registry import ExpertDefinition
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.knowledge.retriever import format_context_for_agent, query_knowledge_result
from src.llm_providers import LLMProvider

Retriever = Callable[..., KnowledgeRetrievalResult]


@dataclass
class _BlindRound:
    memos: list[ExpertMemo] = field(default_factory=list)
    knowledge_status_by_expert: dict[str, KnowledgeStatus] = field(default_factory=dict)
    source_inventory: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _safe_source_inventory(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": str(chunk.get("doc_id", "")),
            "title": str(chunk.get("title", "Unknown")),
            "source_type": str(chunk.get("source_type", "unknown")),
            "chunk_index": int(chunk.get("chunk_index", 0) or 0),
            "score": float(chunk.get("score", 0) or 0),
        }
        for chunk in chunks
    ]


class CouncilOS:
    def __init__(
        self,
        llm: LLMProvider,
        *,
        retriever: Retriever = query_knowledge_result,
        knowledge_namespace: str | None = None,
        knowledge_top_k: int = 5,
    ):
        self.llm = llm
        self.retriever = retriever
        self.knowledge_namespace = (
            knowledge_namespace
            if knowledge_namespace is not None
            else os.getenv("PINECONE_PRIVATE_NAMESPACE") or None
        )
        self.knowledge_top_k = max(1, knowledge_top_k)

    def _retrieve_for_expert(
        self,
        query: str,
        expert: ExpertDefinition,
    ) -> KnowledgeRetrievalResult:
        return self.retriever(
            query,
            top_k=self.knowledge_top_k,
            domains=list(expert.domains),
            experts=list(expert.retrieval_experts),
            namespace=self.knowledge_namespace,
        )

    def _blind_system_prompt(self, expert: ExpertDefinition) -> str:
        return "\n".join(
            [
                "[STAGE:BLIND]",
                f"[EXPERT_ID:{expert.id}]",
                expert.system_prompt,
                "Work independently. You have not seen any other expert's memo or vote.",
                "Return one JSON object only with this schema:",
                "{",
                f'  "expert_id": "{expert.id}",',
                '  "vote": "GO | NO-GO | TEST | DEFER",',
                '  "recommendation": "string",',
                '  "confidence": 0.0,',
                '  "claims": [{"label":"F|A|I|FMW|O","text":"string","source_ids":[]}],',
                '  "assumptions": ["string"],',
                '  "risks": ["string"],',
                '  "what_changes_my_mind": ["string"]',
                "}",
            ]
        )

    def _blind_user_prompt(
        self,
        query: str,
        expert: ExpertDefinition,
        retrieval: KnowledgeRetrievalResult,
    ) -> str:
        context = format_context_for_agent(retrieval.chunks, include_provenance=True)
        return "\n".join(
            [
                f"Decision question: {query}",
                f"Your role: {expert.role}",
                f"Knowledge status: {retrieval.status}",
                "Use the supplied knowledge only when relevant; do not treat frameworks as current facts.",
                "Private knowledge context and provenance:",
                context,
            ]
        )

    async def _generate_blind_memo(
        self,
        query: str,
        expert: ExpertDefinition,
        retrieval: KnowledgeRetrievalResult,
    ) -> ExpertMemo:
        response = await self.llm.generate(
            self._blind_system_prompt(expert),
            self._blind_user_prompt(query, expert, retrieval),
            temperature=0.35,
            max_tokens=1800,
        )
        payload = extract_json_object(response.content)
        payload["expert_id"] = expert.id
        payload["knowledge_status"] = retrieval.status
        return ExpertMemo.model_validate(payload)

    async def _run_blind_memos(
        self,
        query: str,
        experts: list[ExpertDefinition],
    ) -> _BlindRound:
        round_result = _BlindRound()
        retrieval_by_expert: dict[str, KnowledgeRetrievalResult] = {}

        for expert in experts:
            try:
                retrieval = self._retrieve_for_expert(query, expert)
            except Exception as exc:
                retrieval = KnowledgeRetrievalResult(
                    status="unavailable",
                    error_code="retriever_exception",
                )
                round_result.errors.append(f"retrieval:{expert.id}:{type(exc).__name__}")
            retrieval_by_expert[expert.id] = retrieval
            round_result.knowledge_status_by_expert[expert.id] = retrieval.status
            round_result.source_inventory[expert.id] = _safe_source_inventory(retrieval.chunks)

        tasks = [
            self._generate_blind_memo(query, expert, retrieval_by_expert[expert.id])
            for expert in experts
        ]
        generated = await asyncio.gather(*tasks, return_exceptions=True)

        for expert, outcome in zip(experts, generated, strict=True):
            if isinstance(outcome, BaseException):
                round_result.errors.append(f"blind:{expert.id}:{type(outcome).__name__}")
                continue
            round_result.memos.append(outcome)

        return round_result
