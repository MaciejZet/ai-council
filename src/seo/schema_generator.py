"""
Schema Markup Generator
========================
Generuje JSON-LD structured data dla artykułów SEO
Wspiera: Article, FAQ, HowTo
"""

import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FAQItem:
    """Pojedyncze pytanie i odpowiedź dla FAQ schema"""
    question: str
    answer: str


@dataclass
class HowToStep:
    """Krok w instrukcji HowTo"""
    name: str
    text: str
    position: int
    image: str = ""


@dataclass
class SchemaOutput:
    """Wynik generowania schematów"""
    article_schema: Dict[str, Any] = field(default_factory=dict)
    faq_schema: Optional[Dict[str, Any]] = None
    howto_schema: Optional[Dict[str, Any]] = None
    all_schemas: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_json_ld(self) -> str:
        """Zwraca kompletny JSON-LD do osadzenia w HTML"""
        schemas = [s for s in self.all_schemas if s]
        if len(schemas) == 1:
            return json.dumps(schemas[0], ensure_ascii=False, indent=2)
        return json.dumps(schemas, ensure_ascii=False, indent=2)
    
    def to_html_script(self) -> str:
        """Zwraca gotowy tag <script> z JSON-LD"""
        return f'<script type="application/ld+json">\n{self.to_json_ld()}\n</script>'


class SchemaGenerator:
    """
    Generuje JSON-LD structured data dla artykułów
    
    Wspierane typy:
    - Article (BlogPosting, NewsArticle)
    - FAQPage - z sekcji Q&A
    - HowTo - z kroków/instrukcji
    """
    
    def __init__(self, organization_name: str = "", website_url: str = ""):
        self.organization_name = organization_name
        self.website_url = website_url
    
    def generate_all(
        self,
        title: str,
        content: str,
        content_html: str = "",
        author: str = "",
        published_date: str = "",
        modified_date: str = "",
        image_url: str = "",
        article_url: str = "",
        description: str = ""
    ) -> SchemaOutput:
        """
        Generuje wszystkie możliwe schematy dla artykułu
        
        Args:
            title: Tytuł artykułu
            content: Treść w Markdown
            content_html: Treść w HTML (opcjonalnie)
            author: Autor artykułu
            published_date: Data publikacji ISO
            modified_date: Data modyfikacji ISO
            image_url: URL głównego obrazka
            article_url: Canonical URL artykułu
            description: Meta description
            
        Returns:
            SchemaOutput z wszystkimi schematami
        """
        output = SchemaOutput()
        
        # 1. Article schema (zawsze)
        output.article_schema = self.generate_article_schema(
            title=title,
            description=description or self._extract_description(content),
            author=author,
            published_date=published_date or datetime.now().isoformat(),
            modified_date=modified_date,
            image_url=image_url,
            article_url=article_url
        )
        output.all_schemas.append(output.article_schema)
        
        # 2. FAQ schema (jeśli są pytania)
        faq_items = self._extract_faq_items(content)
        if faq_items:
            output.faq_schema = self.generate_faq_schema(faq_items)
            output.all_schemas.append(output.faq_schema)
        
        # 3. HowTo schema (jeśli są kroki)
        howto_steps = self._extract_howto_steps(content)
        if howto_steps:
            howto_title = self._extract_howto_title(content, title)
            output.howto_schema = self.generate_howto_schema(
                name=howto_title,
                steps=howto_steps,
                description=description
            )
            output.all_schemas.append(output.howto_schema)
        
        return output
    
    def generate_article_schema(
        self,
        title: str,
        description: str,
        author: str = "",
        published_date: str = "",
        modified_date: str = "",
        image_url: str = "",
        article_url: str = "",
        article_type: str = "BlogPosting"
    ) -> Dict[str, Any]:
        """Generuje Article/BlogPosting schema"""
        
        schema = {
            "@context": "https://schema.org",
            "@type": article_type,
            "headline": title[:110],  # Google max 110 chars
            "description": description[:320] if description else "",
            "datePublished": published_date or datetime.now().isoformat(),
        }
        
        if modified_date:
            schema["dateModified"] = modified_date
        
        if author:
            schema["author"] = {
                "@type": "Person",
                "name": author
            }
        elif self.organization_name:
            schema["author"] = {
                "@type": "Organization",
                "name": self.organization_name
            }
        
        if self.organization_name:
            schema["publisher"] = {
                "@type": "Organization",
                "name": self.organization_name,
            }
            if self.website_url:
                schema["publisher"]["url"] = self.website_url
        
        if image_url:
            schema["image"] = image_url
        
        if article_url:
            schema["mainEntityOfPage"] = {
                "@type": "WebPage",
                "@id": article_url
            }
        
        return schema
    
    def generate_faq_schema(self, items: List[FAQItem]) -> Dict[str, Any]:
        """Generuje FAQPage schema"""
        
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item.question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item.answer
                    }
                }
                for item in items
            ]
        }
    
    def generate_howto_schema(
        self,
        name: str,
        steps: List[HowToStep],
        description: str = "",
        total_time: str = ""
    ) -> Dict[str, Any]:
        """Generuje HowTo schema"""
        
        schema = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": name,
            "step": [
                {
                    "@type": "HowToStep",
                    "position": step.position,
                    "name": step.name,
                    "text": step.text,
                    **({"image": step.image} if step.image else {})
                }
                for step in steps
            ]
        }
        
        if description:
            schema["description"] = description
        
        if total_time:
            schema["totalTime"] = total_time  # ISO 8601 duration, e.g., "PT30M"
        
        return schema
    
    def _extract_description(self, content: str, max_length: int = 160) -> str:
        """Wyciąga opis z pierwszego akapitu"""
        # Usuń nagłówki
        text = re.sub(r'^#+\s+.+$', '', content, flags=re.MULTILINE)
        # Weź pierwszy niepusty akapit
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paragraphs:
            desc = paragraphs[0][:max_length]
            if len(paragraphs[0]) > max_length:
                desc = desc.rsplit(' ', 1)[0] + '...'
            return desc
        return ""
    
    def _extract_faq_items(self, content: str) -> List[FAQItem]:
        """
        Wyciąga pytania i odpowiedzi z treści
        
        Szuka wzorców:
        - **Pytanie?** Odpowiedź
        - ### Pytanie? \n Odpowiedź
        - Q: Pytanie? A: Odpowiedź
        """
        items = []
        
        # Wzorzec 1: **Pytanie?** Odpowiedź (bold questions)
        pattern1 = r'\*\*([^*]+\?)\*\*\s*\n?\s*([^*\n]+(?:\n(?![*#]).*)*)'
        matches = re.findall(pattern1, content)
        for q, a in matches:
            if len(a.strip()) > 20:  # Min answer length
                items.append(FAQItem(
                    question=q.strip(),
                    answer=a.strip()[:500]
                ))
        
        # Wzorzec 2: ## Pytanie? lub ### Pytanie?
        pattern2 = r'^#{2,3}\s+([^#\n]+\?)\s*\n+([^#]+?)(?=\n#{2,3}|\Z)'
        matches = re.findall(pattern2, content, re.MULTILINE)
        for q, a in matches:
            answer = a.strip()
            # Weź tylko pierwszy akapit jako odpowiedź
            first_para = answer.split('\n\n')[0] if '\n\n' in answer else answer
            if len(first_para) > 20:
                items.append(FAQItem(
                    question=q.strip(),
                    answer=first_para[:500]
                ))
        
        # Usuń duplikaty
        seen = set()
        unique_items = []
        for item in items:
            if item.question not in seen:
                seen.add(item.question)
                unique_items.append(item)
        
        return unique_items[:10]  # Max 10 FAQ items
    
    def _extract_howto_steps(self, content: str) -> List[HowToStep]:
        """
        Wyciąga kroki instrukcji z treści
        
        Szuka wzorców:
        - Numerowane listy: 1. Krok
        - Nagłówki: ## Krok 1: Opis
        """
        steps = []
        
        # Wzorzec 1: ## Krok N: Tytuł lub ## N. Tytuł
        pattern1 = r'^#{2,3}\s+(?:Krok\s+)?(\d+)[.:]\s*(.+)$'
        matches = re.findall(pattern1, content, re.MULTILINE | re.IGNORECASE)
        
        if matches:
            for num, title in matches:
                # Znajdź treść pod tym nagłówkiem
                header_pattern = rf'^#{2,3}\s+(?:Krok\s+)?{num}[.:]\s*.+$'
                parts = re.split(header_pattern, content, flags=re.MULTILINE | re.IGNORECASE)
                
                text = ""
                if len(parts) > 1:
                    # Weź treść do następnego nagłówka
                    next_content = parts[1]
                    text = re.split(r'^#{2,3}\s+', next_content, flags=re.MULTILINE)[0].strip()
                
                steps.append(HowToStep(
                    name=title.strip(),
                    text=text[:500] if text else title.strip(),
                    position=int(num)
                ))
        
        # Wzorzec 2: Numerowana lista Markdown
        if not steps:
            pattern2 = r'^(\d+)\.\s+(.+)$'
            matches = re.findall(pattern2, content, re.MULTILINE)
            
            for i, (num, text) in enumerate(matches, 1):
                if len(text.strip()) > 10:
                    steps.append(HowToStep(
                        name=text.strip()[:100],
                        text=text.strip(),
                        position=i
                    ))
        
        return steps[:15]  # Max 15 steps
    
    def _extract_howto_title(self, content: str, fallback_title: str) -> str:
        """Wyciąga tytuł HowTo z treści"""
        # Szukaj "Jak..." w tytule
        match = re.search(r'^#\s+(Jak\s+.+)$', content, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Szukaj w H1
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1)
        
        return fallback_title


class TableOfContentsGenerator:
    """
    Generuje spis treści (ToC) z nagłówków
    """
    
    def generate(
        self,
        content: str,
        max_level: int = 3,
        include_h1: bool = False
    ) -> Dict[str, Any]:
        """
        Generuje ToC z nagłówków Markdown
        
        Args:
            content: Treść w Markdown
            max_level: Maksymalny poziom nagłówka (2=H2, 3=H2+H3)
            include_h1: Czy uwzględnić H1
            
        Returns:
            Dict z items i html
        """
        items = []
        
        # Znajdź wszystkie nagłówki
        start_level = 1 if include_h1 else 2
        pattern = r'^(#{' + str(start_level) + ',' + str(max_level) + r'})\s+(.+)$'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            hashes = match.group(1)
            text = match.group(2).strip()
            level = len(hashes)
            
            # Generuj anchor ID
            anchor = self._generate_anchor(text)
            
            items.append({
                "level": level,
                "text": text,
                "anchor": anchor
            })
        
        # Generuj HTML
        html = self._generate_html(items)
        
        return {
            "items": items,
            "html": html,
            "count": len(items)
        }
    
    def add_anchors_to_content(self, content: str, max_level: int = 3) -> str:
        """
        Dodaje anchor IDs do nagłówków w Markdown
        Przekształca: ## Tytuł -> ## Tytuł {#tytul}
        """
        def replace_heading(match):
            hashes = match.group(1)
            text = match.group(2).strip()
            anchor = self._generate_anchor(text)
            return f'{hashes} {text} {{#{anchor}}}'
        
        pattern = r'^(#{2,' + str(max_level) + r'})\s+(.+?)(?:\s*\{#[^}]+\})?$'
        return re.sub(pattern, replace_heading, content, flags=re.MULTILINE)
    
    def _generate_anchor(self, text: str) -> str:
        """Generuje anchor ID z tekstu"""
        # Usuń emoji i znaki specjalne
        anchor = re.sub(r'[^\w\s-]', '', text.lower())
        # Zamień spacje na myślniki
        anchor = re.sub(r'\s+', '-', anchor.strip())
        # Usuń wielokrotne myślniki
        anchor = re.sub(r'-+', '-', anchor)
        return anchor[:50]  # Max length
    
    def _generate_html(self, items: List[Dict]) -> str:
        """Generuje HTML dla ToC"""
        if not items:
            return ""
        
        html_parts = ['<nav class="toc"><ul class="toc-list">']
        
        for item in items:
            indent = "  " * (item["level"] - 2)
            html_parts.append(
                f'{indent}<li class="toc-item toc-level-{item["level"]}">'
                f'<a href="#{item["anchor"]}">{item["text"]}</a></li>'
            )
        
        html_parts.append('</ul></nav>')
        return '\n'.join(html_parts)


class FeaturedSnippetOptimizer:
    """
    Optymalizuje treść pod Featured Snippets (pozycja zero)
    """
    
    def optimize(self, content: str, primary_keyword: str = "") -> Dict[str, Any]:
        """
        Analizuje i sugeruje optymalizacje pod Featured Snippets
        
        Returns:
            Dict z optymalizacjami i sugestiami
        """
        result = {
            "definition_box": None,
            "list_snippets": [],
            "table_opportunities": [],
            "suggestions": []
        }
        
        # 1. Definition box - "Co to jest X?"
        definition = self._extract_definition(content, primary_keyword)
        if definition:
            result["definition_box"] = definition
        else:
            result["suggestions"].append(
                f"Dodaj definicję na początku: 'Co to jest {primary_keyword}?'"
            )
        
        # 2. List snippets - listy numerowane/punktowane
        lists = self._extract_lists(content)
        result["list_snippets"] = lists
        
        if not lists:
            result["suggestions"].append(
                "Dodaj numerowaną listę kroków lub listę punktowaną"
            )
        
        # 3. Table opportunities
        tables = self._find_table_opportunities(content)
        result["table_opportunities"] = tables
        
        return result
    
    def create_definition_box(
        self,
        term: str,
        definition: str,
        format_type: str = "paragraph"
    ) -> str:
        """
        Tworzy definition box zoptymalizowany pod Featured Snippet
        
        Args:
            term: Definiowany termin
            definition: Definicja (40-60 słów)
            format_type: "paragraph" lub "list"
        """
        # Ogranicz do 40-60 słów
        words = definition.split()
        if len(words) > 60:
            definition = ' '.join(words[:55]) + '...'
        
        if format_type == "paragraph":
            return f"""**{term}** to {definition}"""
        else:
            return f"""### Co to jest {term}?

{definition}"""
    
    def _extract_definition(self, content: str, keyword: str) -> Optional[Dict]:
        """Szuka definicji w treści"""
        if not keyword:
            return None
        
        # Wzorzec: "X to..." lub "X jest..."
        patterns = [
            rf'\*\*{re.escape(keyword)}\*\*\s+to\s+([^.]+\.)',
            rf'{re.escape(keyword)}\s+to\s+([^.]+\.)',
            rf'{re.escape(keyword)}\s+jest\s+([^.]+\.)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return {
                    "term": keyword,
                    "definition": match.group(1).strip(),
                    "length": len(match.group(1).split())
                }
        
        return None
    
    def _extract_lists(self, content: str) -> List[Dict]:
        """Wyciąga listy potencjalnie nadające się na Featured Snippet"""
        lists = []
        
        # Numerowane listy (szukaj bloków)
        numbered_pattern = r'((?:^\d+\.\s+.+$\n?){3,})'
        for match in re.finditer(numbered_pattern, content, re.MULTILINE):
            list_text = match.group(1)
            items = re.findall(r'^\d+\.\s+(.+)$', list_text, re.MULTILINE)
            if 3 <= len(items) <= 8:  # Optymalna długość
                lists.append({
                    "type": "numbered",
                    "items": items,
                    "count": len(items)
                })
        
        # Punktowane listy
        bullet_pattern = r'((?:^[-*]\s+.+$\n?){3,})'
        for match in re.finditer(bullet_pattern, content, re.MULTILINE):
            list_text = match.group(1)
            items = re.findall(r'^[-*]\s+(.+)$', list_text, re.MULTILINE)
            if 3 <= len(items) <= 8:
                lists.append({
                    "type": "bulleted",
                    "items": items,
                    "count": len(items)
                })
        
        return lists
    
    def _find_table_opportunities(self, content: str) -> List[str]:
        """Identyfikuje miejsca gdzie tabela mogłaby pomóc"""
        suggestions = []
        
        # Szukaj porównań
        if re.search(r'(porówn|vs\.|versus|różnic)', content, re.IGNORECASE):
            suggestions.append("Dodaj tabelę porównawczą")
        
        # Szukaj list cech/właściwości
        if re.search(r'(cech[ay]|właściwoś|parametr|specyfikacj)', content, re.IGNORECASE):
            suggestions.append("Rozważ tabelę specyfikacji/cech")
        
        # Szukaj cenników
        if re.search(r'(cen[ay]|koszt|opłat)', content, re.IGNORECASE):
            suggestions.append("Dodaj tabelę cenową")
        
        return suggestions


if __name__ == "__main__":
    # Test
    test_content = """# Jak wybrać hosting WordPress w 2025?

**Hosting WordPress** to usługa hostingowa zoptymalizowana pod CMS WordPress.

## Co to jest hosting WordPress?

Hosting WordPress to wyspecjalizowana usługa hostingowa, która zapewnia optymalne warunki
do działania stron opartych na systemie WordPress.

## Jak wybrać?

### Krok 1: Określ wymagania

Zanim wybierzesz hosting, musisz określić swoje potrzeby.

### Krok 2: Porównaj oferty

Sprawdź różne opcje na rynku.

### Krok 3: Przetestuj

Większość hostingów oferuje okres próbny.

## Najczęstsze pytania

**Ile kosztuje hosting WordPress?**
Ceny zaczynają się od około 10 zł miesięcznie dla podstawowych planów.

**Czy potrzebuję SSL?**
Tak, certyfikat SSL jest niezbędny dla bezpieczeństwa.
"""

    # Test Schema Generator
    generator = SchemaGenerator(
        organization_name="CometWeb",
        website_url="https://cometweb.pl"
    )
    
    result = generator.generate_all(
        title="Jak wybrać hosting WordPress w 2025?",
        content=test_content,
        author="Jan Kowalski"
    )
    
    print("=== SCHEMA JSON-LD ===")
    print(result.to_json_ld())
    
    # Test ToC
    toc_gen = TableOfContentsGenerator()
    toc = toc_gen.generate(test_content)
    print("\n=== TABLE OF CONTENTS ===")
    print(toc["html"])
    
    # Test Featured Snippet
    snippet_opt = FeaturedSnippetOptimizer()
    snippets = snippet_opt.optimize(test_content, "hosting WordPress")
    print("\n=== FEATURED SNIPPET ===")
    print(json.dumps(snippets, ensure_ascii=False, indent=2))
