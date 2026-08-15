from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpertDefinition:
    id: str
    name: str
    role: str
    domains: tuple[str, ...]
    retrieval_experts: tuple[str, ...]
    routing_keywords: tuple[str, ...]
    system_prompt: str


_EVIDENCE_DISCIPLINE = (
    "Separate every material claim as [F] supplied-evidence fact, [A] assumption, "
    "[I] inference, [FMW] framework-derived claim, or [O] judgment. Do not invent "
    "facts outside the supplied context. State what evidence would change your mind."
)


EXPERT_REGISTRY: dict[str, ExpertDefinition] = {
    "strategy": ExpertDefinition(
        id="strategy",
        name="Strategy",
        role="Competitive strategy and resource allocation",
        domains=("strategy", "business"),
        retrieval_experts=("strategy", "chairman"),
        routing_keywords=(
            "strategy",
            "strategic",
            "competition",
            "competitive",
            "advantage",
            "moat",
            "market entry",
            "expansion",
            "acquire",
            "acquisition",
            "merger",
            "m&a",
            "roadmap",
            "focus",
            "resource allocation",
        ),
        system_prompt=(
            "You are the Strategy expert. Diagnose the real strategic challenge, identify "
            "the decisive constraint, alternatives, opportunity cost, competitive response, "
            "and coherent actions. Avoid generic ambition statements. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "marketing": ExpertDefinition(
        id="marketing",
        name="Marketing & Positioning",
        role="Positioning, category, demand and messaging",
        domains=("marketing", "strategy"),
        retrieval_experts=("marketing", "positioning"),
        routing_keywords=(
            "marketing",
            "positioning",
            "position",
            "brand",
            "branding",
            "message",
            "messaging",
            "category",
            "campaign",
            "awareness",
            "demand",
            "audience",
            "segment",
        ),
        system_prompt=(
            "You are the Marketing & Positioning expert. Evaluate category choice, target "
            "customer, differentiation, message, demand creation, channel-market fit and "
            "brand consequences. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "sales": ExpertDefinition(
        id="sales",
        name="Sales",
        role="Sales motion, buying process and negotiation",
        domains=("sales", "business", "communication"),
        retrieval_experts=("sales", "negotiation"),
        routing_keywords=(
            "sales",
            "pipeline",
            "prospect",
            "prospecting",
            "outbound",
            "negotiation",
            "negotiate",
            "close",
            "closing",
            "buyer",
            "enterprise",
            "deal",
            "quota",
            "sales process",
        ),
        system_prompt=(
            "You are the Sales expert. Evaluate buyer incentives, qualification, buying "
            "process, objections, negotiation leverage, sales-cycle friction and commercial "
            "execution. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "offer_pricing": ExpertDefinition(
        id="offer_pricing",
        name="Offer & Pricing",
        role="Offer design, pricing, packaging and monetization",
        domains=("marketing", "business", "pricing"),
        retrieval_experts=("offer", "pricing", "monetization"),
        routing_keywords=(
            "price",
            "pricing",
            "package",
            "packaging",
            "plan",
            "plans",
            "tier",
            "tiers",
            "offer",
            "monetization",
            "monetise",
            "monetize",
            "willingness to pay",
            "discount",
            "margin",
            "guarantee",
            "upsell",
        ),
        system_prompt=(
            "You are the Offer & Pricing expert. Evaluate the value proposition, value "
            "metric, packaging, price architecture, willingness to pay, margin, risk reversal "
            "and monetization trade-offs. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "product_customer": ExpertDefinition(
        id="product_customer",
        name="Product & Customer",
        role="Customer problem, product value and adoption",
        domains=("business", "innovation", "design"),
        retrieval_experts=("product", "customer", "innovation"),
        routing_keywords=(
            "product",
            "customer",
            "customers",
            "user",
            "users",
            "feature",
            "onboarding",
            "activation",
            "retention",
            "churn",
            "research",
            "customer research",
            "pain",
            "job to be done",
            "jtbd",
            "adoption",
        ),
        system_prompt=(
            "You are the Product & Customer expert. Evaluate the underlying customer job, "
            "pain severity, product evidence, usability, activation, retention, adoption and "
            "whether proposed value exists in observed customer behavior. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "growth": ExpertDefinition(
        id="growth",
        name="Growth",
        role="Acquisition, activation, retention and growth loops",
        domains=("marketing", "business"),
        retrieval_experts=("growth", "marketing"),
        routing_keywords=(
            "growth",
            "acquisition",
            "referral",
            "viral",
            "activation",
            "channel",
            "channels",
            "cac",
            "conversion",
            "funnel",
            "experiment",
            "experimentation",
            "loop",
            "retention",
        ),
        system_prompt=(
            "You are the Growth expert. Evaluate acquisition economics, activation, retention, "
            "referral loops, channel saturation, experiment design and the fastest discriminating "
            "growth test. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "operator": ExpertDefinition(
        id="operator",
        name="Operator",
        role="Execution, ownership, systems and operating cadence",
        domains=("business", "productivity"),
        retrieval_experts=("operator", "operations", "ceo"),
        routing_keywords=(
            "operations",
            "operational",
            "operate",
            "process",
            "implementation",
            "implement",
            "execution",
            "execute",
            "owner",
            "owners",
            "kpi",
            "cadence",
            "sop",
            "hiring",
            "team",
            "workflow",
            "accountability",
        ),
        system_prompt=(
            "You are the Operator. Convert choices into accountable execution: owner, sequence, "
            "dependencies, operating cadence, KPI, failure mode, stop condition and resource "
            "constraint. " + _EVIDENCE_DISCIPLINE
        ),
    ),
    "red_team": ExpertDefinition(
        id="red_team",
        name="Red Team",
        role="Adversarial review and assumption attack",
        domains=("strategy", "psychology", "business"),
        retrieval_experts=("red_team",),
        routing_keywords=(),
        system_prompt=(
            "You are the Red Team. Find hidden incentives, correlated assumptions, base-rate "
            "neglect, second-order effects, irreversible downside, contradictions and credible "
            "ways the preferred plan fails. Build the strongest opposing case. "
            + _EVIDENCE_DISCIPLINE
        ),
    ),
    "evidence_judge": ExpertDefinition(
        id="evidence_judge",
        name="Evidence Judge",
        role="Epistemic quality and provenance review",
        domains=("business",),
        retrieval_experts=("evidence",),
        routing_keywords=(),
        system_prompt=(
            "You are the Evidence Judge. Do not choose the business answer. Classify which claims "
            "are supported by supplied provenance, weak or unsupported, contradictory, or confused "
            "with frameworks. Never equate model agreement with verified fact."
        ),
    ),
    "chairman": ExpertDefinition(
        id="chairman",
        name="Chairman",
        role="Decision synthesis and final recommendation",
        domains=("strategy", "business"),
        retrieval_experts=("chairman", "strategy"),
        routing_keywords=(),
        system_prompt=(
            "You are the Chairman. Decide only after reviewing domain memos, rebuttals, Red Team "
            "and Evidence Judge. Preserve dissent, identify the key uncertainty and choose GO, "
            "NO-GO, TEST or DEFER. Do not conceal evidence gaps."
        ),
    ),
}

DOMAIN_EXPERT_IDS = (
    "strategy",
    "marketing",
    "sales",
    "offer_pricing",
    "product_customer",
    "growth",
    "operator",
)

MANDATORY_REVIEW_ROLE_IDS = ("red_team", "evidence_judge", "chairman")
