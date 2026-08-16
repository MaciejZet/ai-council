from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from src.council.council_os_models import (
    LiveEvidenceContext,
    LiveEvidenceSource,
    ProblemProfile,
)
from src.plugins.web_search import TavilySearchPlugin


class LiveEvidenceProvider(Protocol):
    async def collect(
        self,
        question: str,
        profile: ProblemProfile,
        framework_ids: list[str],
    ) -> LiveEvidenceContext: ...

_MAX_QUERY_CHARS = 320
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER_RE = re.compile(r"\bbearer\s+\S+", re.IGNORECASE)
_NAMED_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_KEYLIKE_RE = re.compile(r"\b(?:sk|pk|key|api)[-_][A-Za-z0-9_-]{16,}\b", re.IGNORECASE)
_OPAQUE_RE = re.compile(r"\b[A-Za-z0-9_-]{48,}\b")
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SPACE_RE = re.compile(r"\s+")

_FOCUS_BY_FRAMEWORK = {
    "strategic_choice": "current market competition strategy",
    "competitive_advantage": "current competitors differentiation",
    "positioning_category": "current category positioning competitors",
    "value_equation": "current pricing offers market",
    "customer_job_evidence": "current customer adoption research",
    "growth_loop": "current acquisition retention growth",
    "operating_constraint": "current operations constraints market",
    "reversibility_experiment": "current market evidence validation",
}
_FOCUS_BY_DOMAIN = {
    "strategy": "current market competition strategy",
    "marketing": "current positioning competitors market",
    "pricing": "current pricing offers market",
    "product_customer": "current customer adoption research",
    "growth": "current acquisition retention growth",
    "operations": "current operations constraints market",
    "business": "current market business conditions",
}


def _strip_url_query(match: re.Match[str]) -> str:
    raw = match.group(0)
    trailing = ""
    while raw and raw[-1] in ".,;:!?)]}":
        trailing = raw[-1] + trailing
        raw = raw[:-1]
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "[REDACTED_URL]" + trailing
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "[REDACTED_URL]" + trailing
    hostname = parsed.hostname.casefold()
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    try:
        port = parsed.port
    except ValueError:
        return "[REDACTED_URL]" + trailing
    if port is not None:
        netloc = f"{netloc}:{port}"
    safe = urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", "", ""))
    return safe + trailing


def sanitize_live_query(question: str) -> str:
    value = _CONTROL_RE.sub(" ", str(question))
    value = _URL_RE.sub(_strip_url_query, value)
    value = _BEARER_RE.sub(" ", value)
    value = _EMAIL_RE.sub(" ", value)
    value = _NAMED_SECRET_RE.sub(" ", value)
    value = _KEYLIKE_RE.sub(" ", value)
    value = _OPAQUE_RE.sub(" ", value)
    value = _SPACE_RE.sub(" ", value).strip(" \t\r\n,;:-")
    return value[:_MAX_QUERY_CHARS].strip()


def _focus_term(profile: ProblemProfile, framework_ids: list[str]) -> str:
    for framework_id in framework_ids:
        if framework_id in _FOCUS_BY_FRAMEWORK:
            return _FOCUS_BY_FRAMEWORK[framework_id]
    return _FOCUS_BY_DOMAIN.get(profile.primary_domain, "current market evidence")


def plan_live_queries(
    question: str,
    profile: ProblemProfile,
    framework_ids: list[str],
) -> list[str]:
    clean = sanitize_live_query(question)
    if not clean:
        return []
    queries = [clean]
    focus = _focus_term(profile, framework_ids)
    focused = f"{clean} {focus}"[:_MAX_QUERY_CHARS].strip()
    if focused.casefold() != clean.casefold():
        queries.append(focused)
    return list(dict.fromkeys(queries))[:2]


def canonicalize_live_url(url: str) -> tuple[str, str]:
    parsed = urlsplit(str(url).strip())
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("unsupported live evidence URL")
    hostname = parsed.hostname.casefold()
    domain = hostname[4:] if hostname.startswith("www.") else hostname
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{hostname}:{parsed.port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, "", "")), domain


def _evidence_id(canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    return f"web_{digest}"


def _clean_text(value: object, limit: int) -> str:
    return _CONTROL_RE.sub("", str(value or "")).strip()[:limit]


def _normalized_title(value: str) -> str:
    return _SPACE_RE.sub(" ", value).strip().casefold()


class TavilyLiveEvidenceProvider:
    def __init__(self, *, search_plugin=None, enabled: bool | None = None):
        self.search_plugin = search_plugin or TavilySearchPlugin()
        if enabled is None:
            enabled = bool(os.getenv("TAVILY_API_KEY") or getattr(self.search_plugin, "_api_key", None))
        self.enabled = bool(enabled)

    async def collect(
        self,
        question: str,
        profile: ProblemProfile,
        framework_ids: list[str],
    ) -> LiveEvidenceContext:
        if not self.enabled:
            return LiveEvidenceContext(status="disabled")

        queries = plan_live_queries(question, profile, framework_ids)
        if not queries:
            return LiveEvidenceContext(
                status="disabled",
                error_labels=["live_query_redacted"],
            )

        fetched_at = datetime.now(timezone.utc).isoformat()
        failed_calls = 0
        candidates: list[LiveEvidenceSource] = []
        for query_index, query in enumerate(queries):
            try:
                result = await self.search_plugin.execute(
                    query,
                    max_results=5,
                    search_depth="basic",
                )
            except Exception:
                failed_calls += 1
                continue
            if not getattr(result, "success", False):
                failed_calls += 1
                continue
            data = getattr(result, "data", None) or {}
            for item in list(data.get("results") or [])[:5]:
                try:
                    canonical_url, domain = canonicalize_live_url(item.get("url", ""))
                except (TypeError, ValueError):
                    continue
                title = _clean_text(item.get("title", ""), 180)
                snippet = _clean_text(item.get("snippet", item.get("content", "")), 600)
                if not title and not snippet:
                    continue
                try:
                    score = float(item.get("score", 0) or 0)
                except (TypeError, ValueError):
                    score = 0.0
                candidates.append(
                    LiveEvidenceSource(
                        evidence_id=_evidence_id(canonical_url),
                        query_index=query_index,
                        title=title,
                        canonical_url=canonical_url,
                        domain=domain,
                        snippet=snippet,
                        relevance_score=score,
                        fetched_at=fetched_at,
                    )
                )

        errors = ["partial_search_failure"] if 0 < failed_calls < len(queries) else []
        if failed_calls == len(queries):
            return LiveEvidenceContext(
                status="unavailable",
                query_count=len(queries),
                error_labels=["live_evidence_unavailable"],
            )

        candidates.sort(
            key=lambda source: (
                -source.relevance_score,
                source.query_index,
                source.canonical_url,
                source.evidence_id,
            )
        )
        unique: list[LiveEvidenceSource] = []
        seen_urls: set[str] = set()
        seen_domain_titles: set[tuple[str, str]] = set()
        for source in candidates:
            title_key = _normalized_title(source.title)
            domain_title = (source.domain, title_key)
            if source.canonical_url in seen_urls:
                continue
            if title_key and domain_title in seen_domain_titles:
                continue
            seen_urls.add(source.canonical_url)
            if title_key:
                seen_domain_titles.add(domain_title)
            unique.append(source)

        if not unique:
            return LiveEvidenceContext(
                status="no_matches",
                query_count=len(queries),
                error_labels=errors,
            )
        return LiveEvidenceContext(
            status="ok",
            query_count=len(queries),
            sources=unique[:10],
            error_labels=errors,
        )
