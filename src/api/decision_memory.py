from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import parse_qs

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.council.council_os_models import CouncilOSResult
from src.storage import user_db as user_store
from src.storage.decision_memory import DecisionMemoryStore

logger = logging.getLogger(__name__)

OutcomeStatus = Literal["success", "failure", "mixed", "inconclusive"]
ResolvedVote = Literal["GO", "NO-GO", "TEST", "DEFER"]
ValidateSession = Callable[[str | None], str | None]


class DecisionOutcomeRequest(BaseModel):
    status: OutcomeStatus
    resolved_vote: ResolvedVote | None = None
    experiment_result: str | None = Field(default=None, max_length=4000)
    postmortem: str | None = Field(default=None, max_length=8000)
    notes: str | None = Field(default=None, max_length=4000)


class DecisionMemoryCaptureMiddleware:
    def __init__(
        self,
        app: Any,
        *,
        store: DecisionMemoryStore,
        validate_session: ValidateSession,
    ):
        self.app = app
        self.store = store
        self.validate_session = validate_session

    @staticmethod
    def _header(scope: dict[str, Any], name: bytes) -> str | None:
        for key, value in scope.get("headers", []):
            if key.lower() == name:
                return value.decode("utf-8", errors="replace")
        return None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("path") != "/api/council/mode/stream":
            await self.app(scope, receive, send)
            return

        query_params = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="replace"))
        mode = (query_params.get("mode") or [""])[0]
        query = (query_params.get("query") or [""])[0]
        if mode != "council_os":
            await self.app(scope, receive, send)
            return

        try:
            user_id = self.validate_session(self._header(scope, b"x-user-session"))
        except Exception:
            logger.warning("Decision Memory session validation failed")
            user_id = None

        if not user_id:
            await self.app(scope, receive, send)
            return

        captured = False

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal captured
            if (
                not captured
                and message.get("type") == "http.response.body"
                and message.get("body")
            ):
                body = message["body"]
                try:
                    text = body.decode("utf-8")
                    updated, did_capture = self._capture_event(text, user_id, query)
                    if did_capture:
                        captured = True
                        message = {**message, "body": updated.encode("utf-8")}
                except Exception:
                    logger.warning("Decision Memory stream capture failed")
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _capture_event(self, text: str, user_id: str, query: str) -> tuple[str, bool]:
        if not text.startswith("data: "):
            return text, False
        raw = text.removeprefix("data: ").strip()
        payload = json.loads(raw)
        if payload.get("event") != "council_os_result" or "result" not in payload:
            return text, False

        try:
            result = CouncilOSResult.model_validate(payload["result"])
            decision_id = self.store.capture_decision(user_id, query, result)
        except Exception:
            logger.warning("Decision Memory persistence failed")
            return text, False

        payload["decision_id"] = decision_id
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n", True


def install_decision_memory(
    app: FastAPI,
    *,
    store: DecisionMemoryStore | None = None,
    validate_session: ValidateSession | None = None,
) -> DecisionMemoryStore:
    if getattr(app.state, "decision_memory_installed", False):
        return app.state.decision_memory_store

    store = store or DecisionMemoryStore()
    validate_session = validate_session or user_store.validate_session
    router = APIRouter(prefix="/api/decision-memory", tags=["decision-memory"])

    def require_user(request: Request) -> str:
        user_id = validate_session(request.headers.get("X-User-Session"))
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or missing X-User-Session")
        return user_id

    @router.get("")
    async def list_decisions(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
        primary_domain: str | None = None,
        verdict: ResolvedVote | None = None,
        outcome_status: OutcomeStatus | None = None,
    ) -> list[dict[str, Any]]:
        user_id = require_user(request)
        return store.list_decisions(
            user_id,
            limit=limit,
            primary_domain=primary_domain,
            verdict=verdict,
            outcome_status=outcome_status,
        )

    @router.get("/calibration")
    async def calibration(request: Request) -> dict[str, Any]:
        user_id = require_user(request)
        return store.calibration_report(user_id)

    @router.get("/{decision_id}")
    async def get_decision(request: Request, decision_id: str) -> dict[str, Any]:
        user_id = require_user(request)
        decision = store.get_decision(user_id, decision_id)
        if decision is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return decision

    @router.put("/{decision_id}/outcome")
    async def put_outcome(
        request: Request,
        decision_id: str,
        body: DecisionOutcomeRequest,
    ) -> dict[str, Any]:
        user_id = require_user(request)
        outcome = store.upsert_outcome(
            user_id,
            decision_id,
            status=body.status,
            resolved_vote=body.resolved_vote,
            experiment_result=body.experiment_result,
            postmortem=body.postmortem,
            notes=body.notes,
        )
        if outcome is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return outcome

    app.include_router(router)
    app.add_middleware(
        DecisionMemoryCaptureMiddleware,
        store=store,
        validate_session=validate_session,
    )
    app.state.decision_memory_installed = True
    app.state.decision_memory_store = store
    return store
