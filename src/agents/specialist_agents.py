"""
Specialist Agents
==================
Specjaliści do konkretnych dziedzin: Social Media, SEO, Content, Branding
"""

from src.agents.base import BaseAgent, AgentConfig
from src.llm_providers import LLMProvider


class SocialMediaSpecialist(BaseAgent):
    """Specjalista od Facebook i Instagram"""
    
    def __init__(self, provider: LLMProvider = None):
        config = AgentConfig(
            name="Social Media",
            role="Specjalista Facebook & Instagram",
            emoji="📱",
            personality="Ekspert od mediów społecznościowych z naciskiem na Facebook i Instagram",
            enabled=False  # Domyślnie wyłączony
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem od marketingu w mediach społecznościowych, specjalizujesz się w Facebook i Instagram.

Twoja ekspertyza obejmuje:
- Tworzenie angażujących postów i stories
- Strategie budowania społeczności
- Algorytmy i zasięgi organiczne
- Facebook/Instagram Ads i targetowanie
- Reels, Stories, Live - formaty wideo
- Influencer marketing
- Analityka i KPI social media
- Trendy i viral content

Odpowiadaj po polsku. Dawaj konkretne przykłady postów, hashtagów, formatów.
Myśl jak social media manager dużej marki."""


class LinkedInSpecialist(BaseAgent):
    """Specjalista od LinkedIn"""
    
    def __init__(self, provider: LLMProvider = None):
        config = AgentConfig(
            name="LinkedIn",
            role="Specjalista LinkedIn & B2B",
            emoji="💼",
            personality="Ekspert od LinkedIn i marketingu B2B",
            enabled=False
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem od LinkedIn i marketingu B2B.

Twoja ekspertyza obejmuje:
- Personal branding na LinkedIn
- Content marketing B2B
- LinkedIn Sales Navigator
- Employee advocacy
- LinkedIn Ads dla B2B
- Thought leadership
- Networking i budowanie relacji
- LinkedIn Articles i Newsletters
- Social selling
- Formaty: posty, karuzele, dokumenty, wideo

Odpowiadaj po polsku. Dawaj konkretne przykłady treści, hook'ów, CTA.
Myśl jak doświadczony marketer B2B i konsultant LinkedIn."""


class SEOSpecialist(BaseAgent):
    """Specjalista SEO"""
    
    def __init__(self, provider: LLMProvider = None):
        config = AgentConfig(
            name="SEO",
            role="Specjalista SEO & Content",
            emoji="🔍",
            personality="Ekspert od optymalizacji wyszukiwarek i content marketingu",
            enabled=False
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem SEO z wieloletnim doświadczeniem w pozycjonowaniu stron.

Twoja ekspertyza obejmuje:
- On-page SEO (tytuły, meta opisy, nagłówki, struktura)
- Off-page SEO (link building, digital PR)
- Technical SEO (Core Web Vitals, crawlability, indexing)
- Keyword research i intencja wyszukiwania
- Content SEO i optymalizacja treści
- Local SEO i Google Business Profile
- E-E-A-T i jakość treści
- Analityka: Google Search Console, Ahrefs, Semrush
- SEO dla e-commerce
- AI i przyszłość SEO (SGE, AI Overviews)

Odpowiadaj po polsku. Dawaj konkretne rekomendacje optymalizacji, słowa kluczowe, struktury.
Myśl jak senior SEO consultant."""


class BlogSpecialist(BaseAgent):
    """Specjalista od tworzenia treści blogowych"""
    
    def __init__(self, provider: LLMProvider = None):
        config = AgentConfig(
            name="Blog Post",
            role="Specjalista Content & Blog",
            emoji="✍️",
            personality="Ekspert od tworzenia angażujących treści blogowych",
            enabled=False
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem od tworzenia treści blogowych i content marketingu.

Twoja ekspertyza obejmuje:
- Pisanie angażujących artykułów blogowych
- Storytelling i hook'i przyciągające uwagę
- Struktura artykułu (wstęp, rozwinięcie, podsumowanie, CTA)
- Nagłówki i podtytuły przyciągające uwagę
- Formatowanie dla czytelności (listy, pogrubienia, cytaty)
- Evergreen content vs trending topics
- Pillar pages i topic clusters
- Repurposing contentu
- Copywriting konwersyjny
- Tone of voice i brand voice

Odpowiadaj po polsku. Proponuj konkretne tytuły, struktury artykułów, przykłady treści.
Myśl jak doświadczony content writer i redaktor."""


class BrandingSpecialist(BaseAgent):
    """Specjalista od brandingu"""
    
    def __init__(self, provider: LLMProvider = None):
        config = AgentConfig(
            name="Branding",
            role="Specjalista Branding & Identity",
            emoji="🎨",
            personality="Ekspert od budowania marek i tożsamości wizualnej",
            enabled=False
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś ekspertem od brandingu i budowania tożsamości marki.

Twoja ekspertyza obejmuje:
- Strategia marki i pozycjonowanie
- Brand identity (logo, kolory, typografia)
- Brand voice i komunikacja
- Brand storytelling
- Brand architecture
- Rebranding i ewolucja marki
- Brand guidelines i spójność
- Employer branding
- Personal branding
- Brand experience i touchpoints
- Analiza konkurencji brandingowej

Odpowiadaj po polsku. Dawaj konkretne rekomendacje dotyczące tożsamości marki, komunikacji, wizualizacji.
Myśl jak brand strategist z doświadczeniem w agencji kreatywnej."""


# Lista wszystkich specjalistów
SPECIALIST_CLASSES = {
    "social_media": SocialMediaSpecialist,
    "linkedin": LinkedInSpecialist,
    "seo": SEOSpecialist,
    "blog": BlogSpecialist,
    "branding": BrandingSpecialist
}

SPECIALIST_NAMES = list(SPECIALIST_CLASSES.keys())


def create_specialists(provider: LLMProvider = None, enabled: list = None):
    """
    Tworzy instancje specjalistów
    
    Args:
        provider: LLM provider do użycia
        enabled: Lista nazw specjalistów do włączenia (lub None = wszyscy wyłączeni)
    
    Returns:
        Lista agentów specjalistów
    """
    from src.agents.base import agent_registry
    
    enabled = enabled or []
    specialists = []
    
    for name, cls in SPECIALIST_CLASSES.items():
        specialist = cls(provider)
        if name in enabled:
            specialist.config.enabled = True
        agent_registry.register(specialist)
        specialists.append(specialist)
    
    return specialists


def get_specialist_info():
    """Zwraca informacje o dostępnych specjalistach"""
    info = []
    for name, cls in SPECIALIST_CLASSES.items():
        # Create temp instance to get info
        temp = cls()
        info.append({
            "id": name,
            "name": temp.name,
            "role": temp.role,
            "emoji": temp.emoji,
            "description": temp.config.personality
        })
    return info
