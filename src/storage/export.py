"""
Session Export
===============
Export sesji do Markdown i PDF
"""

from datetime import datetime
from typing import Optional
from pathlib import Path
import io

from .session_history import SessionData, session_history


def export_to_markdown(session: SessionData) -> str:
    """
    Eksportuje sesję do formatu Markdown
    
    Returns:
        String z treścią Markdown
    """
    md = []
    meta = session.metadata
    
    # Header
    md.append(f"# 🏛️ Narada Rady AI")
    md.append("")
    md.append(f"**Data:** {_format_date(meta.timestamp)}")
    md.append(f"**Tryb:** {meta.council_type}")
    md.append(f"**Model:** {meta.provider} / {meta.model}")
    md.append(f"**Agenci:** {', '.join(meta.agents_used)}")
    md.append("")
    md.append("---")
    md.append("")
    
    # Query
    md.append("## 💬 Zapytanie")
    md.append("")
    md.append(f"> {meta.query}")
    md.append("")
    
    # Sources (if any)
    if session.sources:
        md.append("## 📚 Źródła z bazy wiedzy")
        md.append("")
        for source in session.sources:
            title = source.get("title", "Dokument")
            page = source.get("page", "")
            page_str = f" (str. {page})" if page else ""
            md.append(f"- {title}{page_str}")
        md.append("")
    
    # Agent responses
    md.append("## 👥 Odpowiedzi Agentów")
    md.append("")
    
    for resp in session.responses:
        agent_name = resp.get("agent_name", "Agent")
        role = resp.get("role", "")
        content = resp.get("content", "")
        
        md.append(f"### {agent_name}")
        if role:
            md.append(f"*{role}*")
        md.append("")
        md.append(content)
        md.append("")
    
    # Synthesis
    if session.synthesis:
        md.append("## 🔮 Synteza Końcowa")
        md.append("")
        md.append(session.synthesis)
        md.append("")
    
    # Footer
    md.append("---")
    md.append("")
    md.append(f"*Wygenerowano przez AI Council • Tokeny: {meta.total_tokens} • Koszt: ${meta.cost_usd:.4f}*")
    
    return "\n".join(md)


def export_to_html(session: SessionData) -> str:
    """
    Eksportuje sesję do HTML (dla konwersji do PDF)
    
    Returns:
        String z treścią HTML
    """
    meta = session.metadata
    
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Narada Rady AI - {_format_date(meta.timestamp)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #fff;
        }}
        h1 {{
            color: #1a1a2e;
            font-size: 28px;
            margin-bottom: 20px;
            border-bottom: 3px solid #3b19e6;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #3b19e6;
            font-size: 20px;
            margin: 30px 0 15px 0;
        }}
        h3 {{
            color: #333;
            font-size: 16px;
            margin: 20px 0 10px 0;
            padding: 8px 12px;
            background: #f0f0f5;
            border-radius: 6px;
        }}
        .meta {{
            background: #f8f8fc;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #666;
        }}
        .meta span {{
            display: inline-block;
            margin-right: 20px;
        }}
        .query {{
            background: linear-gradient(135deg, #3b19e6 0%, #6b4fe6 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            font-size: 16px;
        }}
        .agent {{
            background: #fafafa;
            border: 1px solid #eee;
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
        }}
        .agent-name {{
            font-weight: 600;
            color: #3b19e6;
            font-size: 15px;
        }}
        .agent-role {{
            font-size: 13px;
            color: #888;
            font-style: italic;
            margin-bottom: 10px;
        }}
        .agent-content {{
            white-space: pre-wrap;
            font-size: 14px;
        }}
        .synthesis {{
            background: linear-gradient(135deg, #1a1a2e 0%, #2a2a4e 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            margin: 30px 0;
        }}
        .synthesis h2 {{
            color: #ffd700;
            margin-top: 0;
        }}
        .synthesis-content {{
            white-space: pre-wrap;
            font-size: 14px;
        }}
        .sources {{
            font-size: 13px;
            color: #666;
        }}
        .sources ul {{
            list-style: none;
            padding-left: 0;
        }}
        .sources li {{
            padding: 5px 0;
            border-bottom: 1px dashed #ddd;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>🏛️ Narada Rady AI</h1>
    
    <div class="meta">
        <span><strong>Data:</strong> {_format_date(meta.timestamp)}</span>
        <span><strong>Tryb:</strong> {meta.council_type}</span>
        <span><strong>Model:</strong> {meta.provider} / {meta.model}</span>
    </div>
    
    <h2>💬 Zapytanie</h2>
    <div class="query">{_escape_html(meta.query)}</div>
"""
    
    # Sources
    if session.sources:
        html += """
    <div class="sources">
        <h2>📚 Źródła z bazy wiedzy</h2>
        <ul>
"""
        for source in session.sources:
            title = _escape_html(source.get("title", "Dokument"))
            page = source.get("page", "")
            page_str = f" (str. {page})" if page else ""
            html += f"            <li>{title}{page_str}</li>\n"
        html += "        </ul>\n    </div>\n"
    
    # Agents
    html += """
    <h2>👥 Odpowiedzi Agentów</h2>
"""
    for resp in session.responses:
        agent_name = _escape_html(resp.get("agent_name", "Agent"))
        role = _escape_html(resp.get("role", ""))
        content = _escape_html(resp.get("content", ""))
        
        html += f"""
    <div class="agent">
        <div class="agent-name">{agent_name}</div>
        <div class="agent-role">{role}</div>
        <div class="agent-content">{content}</div>
    </div>
"""
    
    # Synthesis
    if session.synthesis:
        html += f"""
    <div class="synthesis">
        <h2>🔮 Synteza Końcowa</h2>
        <div class="synthesis-content">{_escape_html(session.synthesis)}</div>
    </div>
"""
    
    # Footer
    html += f"""
    <div class="footer">
        Wygenerowano przez AI Council • Tokeny: {meta.total_tokens} • Koszt: ${meta.cost_usd:.4f}
    </div>
</body>
</html>
"""
    return html


def export_to_pdf(session: SessionData) -> Optional[bytes]:
    """
    Eksportuje sesję do PDF
    
    Returns:
        Bytes z plikiem PDF lub None jeśli błąd
    """
    try:
        from weasyprint import HTML
        html_content = export_to_html(session)
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes
    except ImportError:
        # Fallback - zwróć HTML jeśli weasyprint niedostępny
        return None
    except Exception as e:
        print(f"PDF export error: {e}")
        return None


def _format_date(iso_timestamp: str) -> str:
    """Formatuje datę z ISO do czytelnej formy"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%d.%m.%Y, %H:%M")
    except (ValueError, TypeError) as e:
        print(f"⚠️ Date parsing failed for '{iso_timestamp}': {e}")
        return iso_timestamp


def _escape_html(text: str) -> str:
    """Escapuje znaki HTML"""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br>")
    )
