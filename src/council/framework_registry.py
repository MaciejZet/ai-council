from __future__ import annotations

from dataclasses import dataclass

FRAMEWORK_POLICY_VERSION = "framework-selector-v1"


@dataclass(frozen=True)
class FrameworkDefinition:
    id: str
    name: str
    domains: tuple[str, ...]
    decision_kinds: tuple[str, ...]
    expert_ids: tuple[str, ...]
    trigger_keywords: tuple[str, ...]
    framework_tags: tuple[str, ...]
    diagnostic_questions: tuple[str, ...]
    description: str


FRAMEWORK_REGISTRY: dict[str, FrameworkDefinition] = {
    "strategic_choice": FrameworkDefinition(
        id="strategic_choice",
        name="Strategic choice",
        domains=("strategy", "business"),
        decision_kinds=("strategy",),
        expert_ids=("strategy", "operator", "chairman"),
        trigger_keywords=(
            "strategy", "strategic", "market entry", "focus", "resource allocation",
            "trade-off", "tradeoff", "choice", "strategia", "alokacja zasobów",
        ),
        framework_tags=("strategic_choice", "good_strategy", "resource_allocation"),
        diagnostic_questions=(
            "What is the decisive constraint or challenge?",
            "Which real alternative is being rejected?",
            "What actions must reinforce one another for the choice to work?",
        ),
        description="Clarifies the real strategic challenge, explicit choice, trade-offs, and the coherent actions needed to make the choice work.",
    ),
    "competitive_advantage": FrameworkDefinition(
        id="competitive_advantage",
        name="Competitive advantage",
        domains=("strategy", "innovation", "business"),
        decision_kinds=(),
        expert_ids=("strategy", "product_customer", "chairman"),
        trigger_keywords=(
            "advantage", "competitive", "moat", "different", "differentiation",
            "competitor", "konkurencja", "przewaga", "wyróżnik",
        ),
        framework_tags=("competitive_advantage", "moat", "zero_to_one"),
        diagnostic_questions=(
            "What is meaningfully different from the closest substitute?",
            "Why would that advantage persist after competitors respond?",
            "Which assumption would make the claimed advantage disappear?",
        ),
        description="Tests whether a proposal creates a durable reason to win after substitutes and competitors respond.",
    ),
    "positioning_category": FrameworkDefinition(
        id="positioning_category",
        name="Positioning and category",
        domains=("marketing", "strategy"),
        decision_kinds=("marketing",),
        expert_ids=("marketing", "sales"),
        trigger_keywords=(
            "positioning", "position", "category", "segment", "message", "brand",
            "pozycjonowanie", "kategoria", "segment", "marka", "komunikat",
        ),
        framework_tags=("positioning", "category", "marketing_laws"),
        diagnostic_questions=(
            "What category does the buyer use to understand this offer?",
            "What is the clearest contrast with the main alternative?",
            "Which customer segment is most likely to care about that contrast now?",
        ),
        description="Clarifies category, target customer, contrast, and the message a buyer should use to place the offer in context.",
    ),
    "value_equation": FrameworkDefinition(
        id="value_equation",
        name="Value equation",
        domains=("pricing", "marketing", "business"),
        decision_kinds=("pricing",),
        expert_ids=("offer_pricing", "sales", "marketing"),
        trigger_keywords=(
            "price", "pricing", "package", "packaging", "offer", "value", "margin",
            "guarantee", "cena", "ceny", "pakiet", "oferta", "marża",
        ),
        framework_tags=("value_equation", "offer", "pricing", "risk_reversal"),
        diagnostic_questions=(
            "Which outcome matters enough to pay for?",
            "What slows the buyer's path to that outcome?",
            "Which effort, risk, or uncertainty suppresses perceived value?",
        ),
        description="Stress-tests perceived value, speed to outcome, effort, risk, packaging, and price logic from the buyer's perspective.",
    ),
    "customer_job_evidence": FrameworkDefinition(
        id="customer_job_evidence",
        name="Customer job and evidence",
        domains=("business", "innovation", "design"),
        decision_kinds=("product_customer",),
        expert_ids=("product_customer", "growth"),
        trigger_keywords=(
            "customer", "user", "job to be done", "jtbd", "pain", "adoption", "research",
            "klient", "użytkownik", "problem", "badania klientów", "adopcja",
        ),
        framework_tags=("jtbd", "customer_research", "problem_evidence"),
        diagnostic_questions=(
            "What job is the customer already trying to complete?",
            "What current behavior proves the problem matters?",
            "What evidence would show that the proposed solution is not the real answer?",
        ),
        description="Separates a product idea from evidence that a real customer job, pain, and adoption behavior exist.",
    ),
    "growth_loop": FrameworkDefinition(
        id="growth_loop",
        name="Growth loop",
        domains=("marketing", "business"),
        decision_kinds=("growth",),
        expert_ids=("growth", "marketing", "product_customer"),
        trigger_keywords=(
            "growth", "referral", "viral", "loop", "acquisition", "retention", "activation",
            "wzrost", "polecenia", "akwizycja", "retencja", "aktywacja",
        ),
        framework_tags=("growth_loop", "acquisition", "retention", "referral"),
        diagnostic_questions=(
            "What user action creates the next unit of growth?",
            "Where does the loop lose energy?",
            "Which metric would prove the loop compounds rather than merely spikes?",
        ),
        description="Tests whether acquisition, activation, retention, and referrals reinforce one another instead of producing isolated spikes.",
    ),
    "operating_constraint": FrameworkDefinition(
        id="operating_constraint",
        name="Operating constraint",
        domains=("business", "productivity"),
        decision_kinds=("operations",),
        expert_ids=("operator", "strategy"),
        trigger_keywords=(
            "operations", "operational", "bottleneck", "constraint", "execution", "owner", "kpi",
            "operacje", "wąskie gardło", "ograniczenie", "wdrożenie", "właściciel",
        ),
        framework_tags=("operations", "constraint", "execution", "principles"),
        diagnostic_questions=(
            "What is the current bottleneck?",
            "Who owns the next irreversible or gating step?",
            "Which signal should trigger a stop, escalation, or resource shift?",
        ),
        description="Turns a recommendation into an executable sequence around the primary bottleneck, ownership, and stop conditions.",
    ),
    "reversibility_experiment": FrameworkDefinition(
        id="reversibility_experiment",
        name="Reversibility and experiment",
        domains=("strategy", "business", "marketing", "innovation", "productivity"),
        decision_kinds=(),
        expert_ids=("growth", "product_customer", "operator", "strategy"),
        trigger_keywords=(
            "experiment", "test", "pilot", "reversible", "validate", "hypothesis",
            "eksperyment", "test", "pilotaż", "odwracalny", "hipoteza",
        ),
        framework_tags=("experiment", "reversibility", "test", "decision_making"),
        diagnostic_questions=(
            "Which assumption currently drives the decision most strongly?",
            "What is the cheapest test that could falsify it?",
            "What threshold would justify scaling, stopping, or deferring?",
        ),
        description="Chooses the smallest reversible action that can resolve the key uncertainty before a larger commitment.",
    ),
}
