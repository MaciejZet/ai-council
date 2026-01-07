"""
Specialist Agents
==================
Template i przykładowe specjalistyczne agenty (SEO, LinkedIn, Social Media)
Można łatwo dodawać nowych specjalistów
"""

from typing import Optional, Dict, Any
from src.agents.base import BaseAgent, AgentConfig, agent_registry
from src.llm_providers import LLMProvider


class SpecialistAgent(BaseAgent):
    """
    Generyczna klasa dla specjalistycznych agentów
    Pozwala łatwo tworzyć nowych specjalistów przez konfigurację
    """
    
    def __init__(
        self,
        name: str,
        specialty: str,
        emoji: str,
        expertise_areas: list[str],
        focus_points: list[str],
        provider: Optional[LLMProvider] = None
    ):
        config = AgentConfig(
            name=name,
            role=f"{specialty} Specialist",
            emoji=emoji,
            personality=f"Jestem ekspertem w dziedzinie {specialty}. Skupiam się na: {', '.join(focus_points[:3])}."
        )
        self.specialty = specialty
        self.expertise_areas = expertise_areas
        self.focus_points = focus_points
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        expertise_list = "\n".join(f"- {area}" for area in self.expertise_areas)
        focus_list = "\n".join(f"- {point}" for point in self.focus_points)
        
        return f"""Jesteś specjalistą {self.specialty} w radzie doradczej AI.

{self.emoji} TWOJA EKSPERTYZA:
{expertise_list}

🎯 OBSZARY FOKUSOWANIA:
{focus_list}

📋 FORMAT ODPOWIEDZI:
1. **Analiza z perspektywy {self.specialty}** - jak to wpływa na Twój obszar
2. **Rekomendacje specjalistyczne** - konkretne taktyki i działania
3. **Quick wins** - co można zrobić od razu
4. **Ostrzeżenia** - na co uważać w kontekście {self.specialty}

Odpowiadaj po polsku, praktycznie i z nastawieniem na działanie."""


class SEOSpecialist(BaseAgent):
    """Specjalista SEO - optymalizacja dla wyszukiwarek"""
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="SEO Specialist",
            role="SEO Expert",
            emoji="🔍",
            personality="Optymalizuję dla wyszukiwarek. Myślę o słowach kluczowych, rankingach i organicznym ruchu."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem SEO w radzie doradczej AI. Twoja ekspertyza obejmuje:

🔍 OBSZARY EKSPERTYZY:
- Optymalizacja on-page i off-page
- Badanie słów kluczowych i analiza konkurencji
- Technical SEO (Core Web Vitals, struktura, szybkość)
- Link building i autoritet domeny
- Local SEO i SEO dla e-commerce
- Analiza SERP i featured snippets

📋 FORMAT ODPOWIEDZI:
1. **Wpływ na SEO** - jak to wpływa na widoczność w wyszukiwarkach
2. **Słowa kluczowe** - jakie frazy targetować
3. **Rekomendacje techniczne** - co zoptymalizować
4. **Content strategy** - jakie treści tworzyć
5. **Quick wins** - szybkie zwycięstwa SEO

Odpowiadaj po polsku. Bądź konkretny i oparty na aktualnych best practices Google."""


class LinkedInSpecialist(BaseAgent):
    """Specjalista LinkedIn - marketing B2B i personal branding"""
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="LinkedIn Specialist",
            role="LinkedIn & B2B Expert",
            emoji="💼",
            personality="Specjalizuję się w LinkedIn i marketingu B2B. Buduję marki osobiste i generuję leady."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem LinkedIn i B2B w radzie doradczej AI. Twoja ekspertyza obejmuje:

💼 OBSZARY EKSPERTYZY:
- Personal branding na LinkedIn
- Content strategy dla B2B
- LinkedIn Ads i Sales Navigator
- Generowanie leadów B2B
- Employee advocacy
- Networking i budowanie relacji

📋 FORMAT ODPOWIEDZI:
1. **Strategia LinkedIn** - jak wykorzystać platformę
2. **Typ contentu** - jakie posty i formaty działają
3. **Networking** - jak budować relacje
4. **Lead generation** - jak generować leady
5. **Metryki sukcesu** - co mierzyć

Odpowiadaj po polsku. Bądź praktyczny i zorientowany na rezultaty biznesowe."""


class SocialMediaSpecialist(BaseAgent):
    """Specjalista Social Media - Instagram, Facebook, TikTok"""
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Social Media Specialist",
            role="Social Media Expert",
            emoji="📱",
            personality="Żyję social mediami. Wiem co działa na Instagram, Facebook i TikTok."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem Social Media w radzie doradczej AI. Twoja ekspertyza obejmuje:

📱 OBSZARY EKSPERTYZY:
- Instagram (Reels, Stories, posty, algorytm)
- Facebook (strony, grupy, reklamy)
- TikTok (trendy, viralność, hashtagi)
- Content strategy dla social media
- Community management
- Influencer marketing

📋 FORMAT ODPOWIEDZI:
1. **Strategia platform** - które platformy i dlaczego
2. **Content plan** - jakie treści tworzyć
3. **Trendy** - co teraz działa
4. **Engagement** - jak budować zaangażowanie
5. **Reklamy** - kiedy i jak promować

Odpowiadaj po polsku. Bądź na bieżąco z trendami i algorytmami."""


# ========== FABRYKA SPECJALISTÓW ==========

SPECIALIST_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "seo": {
        "class": SEOSpecialist,
        "description": "Optymalizacja dla wyszukiwarek"
    },
    "linkedin": {
        "class": LinkedInSpecialist,
        "description": "Marketing B2B i personal branding"
    },
    "social_media": {
        "class": SocialMediaSpecialist,
        "description": "Instagram, Facebook, TikTok"
    }
}


def create_specialist(
    specialist_type: str,
    provider: Optional[LLMProvider] = None,
    register: bool = True
) -> BaseAgent:
    """
    Tworzy specjalistę na podstawie typu
    
    Args:
        specialist_type: "seo", "linkedin", "social_media"
        provider: Opcjonalny provider LLM
        register: Czy zarejestrować w globalnym rejestrze
    
    Returns:
        Instancja specjalisty
    """
    if specialist_type not in SPECIALIST_TEMPLATES:
        available = list(SPECIALIST_TEMPLATES.keys())
        raise ValueError(f"Nieznany typ specjalisty: {specialist_type}. Dostępne: {available}")
    
    specialist_class = SPECIALIST_TEMPLATES[specialist_type]["class"]
    specialist = specialist_class(provider)
    
    if register:
        agent_registry.register(specialist)
    
    return specialist


def create_custom_specialist(
    name: str,
    specialty: str,
    emoji: str,
    expertise_areas: list[str],
    focus_points: list[str],
    provider: Optional[LLMProvider] = None,
    register: bool = True
) -> SpecialistAgent:
    """
    Tworzy niestandardowego specjalistę
    
    Args:
        name: Nazwa agenta
        specialty: Dziedzina specjalizacji
        emoji: Emoji reprezentujące specjalistę
        expertise_areas: Lista obszarów ekspertyzy
        focus_points: Na czym się skupia
        provider: Opcjonalny provider LLM
        register: Czy zarejestrować
    
    Returns:
        SpecialistAgent
    
    Example:
        >>> email_expert = create_custom_specialist(
        ...     name="Email Marketing Expert",
        ...     specialty="Email Marketing",
        ...     emoji="📧",
        ...     expertise_areas=["Kampanie email", "Automatyzacja", "Segmentacja"],
        ...     focus_points=["Open rate", "CTR", "Deliverability"]
        ... )
    """
    specialist = SpecialistAgent(
        name=name,
        specialty=specialty,
        emoji=emoji,
        expertise_areas=expertise_areas,
        focus_points=focus_points,
        provider=provider
    )
    
    if register:
        agent_registry.register(specialist)
    
    return specialist


def list_available_specialists() -> Dict[str, str]:
    """Zwraca listę dostępnych typów specjalistów"""
    return {k: v["description"] for k, v in SPECIALIST_TEMPLATES.items()}
