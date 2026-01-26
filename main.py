"""
AI Council - FastAPI Backend
=============================
REST API dla wieloagentowej rady AI
"""

import asyncio
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response
from pydantic import BaseModel

# Import existing modules
from src.agents.base import agent_registry
from src.agents.core_agents import create_core_agents, CORE_AGENT_NAMES, Strategist, Analyst, Practitioner, Expert, Synthesizer
from src.agents.specialist_agents import create_specialists, get_specialist_info, SPECIALIST_CLASSES
from src.agents.custom_agents import CustomAgentConfig, CustomAgent, create_custom_agent, get_custom_agent_info
from src.agents import agent_storage
from src.agents.prompt_templates import get_all_templates, get_template, get_templates_by_category
from src.council.orchestrator import Council, CouncilDeliberation, format_deliberation_markdown
from src.council.debate import DebateOrchestrator
from src.knowledge.ingest import ingest_pdf, get_ingestion_stats
from src.knowledge.retriever import get_category_emoji, query_knowledge, format_sources_for_display
from src.council.debate import DebateOrchestrator
from src.knowledge.ingest import ingest_pdf, get_ingestion_stats
from src.knowledge.retriever import get_category_emoji, query_knowledge, format_sources_for_display
from src.llm_providers import OpenAIProvider, GrokProvider, GeminiProvider, DeepSeekProvider, OpenRouterProvider, AVAILABLE_PROVIDERS, get_provider
from src.plugins import get_plugin_manager, PluginResult
from src.plugins.web_search import TavilySearchPlugin, DuckDuckGoSearchPlugin
from src.plugins.url_analyzer import URLAnalyzerPlugin
from src.plugins.wikipedia import WikipediaPlugin
from src.plugins.weather import WeatherPlugin
from src.plugins.stocks import StockPricesPlugin
from src.plugins.utilities import (
    CalculatorPlugin, DateTimePlugin, HashEncodePlugin,
    UnitConverterPlugin, RandomGeneratorPlugin, TextToolsPlugin
)


# ========== MODELS ==========
class DeliberateRequest(BaseModel):
    query: str
    provider: str = "openai"
    model: str = "gpt-4o"
    use_knowledge_base: bool = True
    chat_mode: bool = False
    attachment_text: str = ""
    history: Optional[List[dict]] = None


class AgentInfo(BaseModel):
    name: str
    role: str
    emoji: str
    enabled: bool
    description: str


class AgentToggleRequest(BaseModel):
    enabled: bool


class UsageData(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class AgentResponseData(BaseModel):
    agent_name: str
    role: str
    content: str
    provider_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


class SourceData(BaseModel):
    title: str
    category: str
    max_score: float
    emoji: str


class DeliberationResult(BaseModel):
    query: str
    timestamp: str
    agent_responses: List[AgentResponseData]
    synthesis: Optional[AgentResponseData]
    sources: List[SourceData]
    total_agents: int
    usage: UsageData = UsageData()


class CustomAgentRequest(BaseModel):
    name: str
    emoji: str = "🤖"
    role: str = "Custom Agent"
    persona: str = ""
    system_prompt: str = ""
    template_id: Optional[str] = None
    tools: List[str] = []
    context_limit: int = 5000
    memory_type: str = "session"
    enabled: bool = True


class AgentTestRequest(BaseModel):
    config: CustomAgentRequest
    query: str
    provider: str = "openai"
    model: str = "gpt-4o"


# ========== APP SETUP ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize core agents and specialists on startup
    create_core_agents()
    create_specialists()  # Create all specialists (disabled by default)
    
    # Register plugins
    pm = get_plugin_manager()
    pm.register("tavily", TavilySearchPlugin())
    pm.register("duckduckgo", DuckDuckGoSearchPlugin())
    pm.register("url_analyzer", URLAnalyzerPlugin())
    pm.register("wikipedia", WikipediaPlugin())
    pm.register("weather", WeatherPlugin())
    pm.register("stocks", StockPricesPlugin())
    pm.register("calculator", CalculatorPlugin())
    pm.register("datetime", DateTimePlugin())
    pm.register("hash", HashEncodePlugin())
    pm.register("converter", UnitConverterPlugin())
    pm.register("random", RandomGeneratorPlugin())
    pm.register("text", TextToolsPlugin())
    
    yield

app = FastAPI(title="AI Council API", lifespan=lifespan)

# Static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ========== ROUTES ==========
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main UI"""
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>AI Council</h1><p>Frontend not found. Check static/index.html</p>")


@app.get("/api/agents", response_model=List[AgentInfo])
async def get_agents():
    """Get all registered agents with status (core + specialists)"""
    agents = agent_registry.get_all()
    
    descriptions = {
        # Core agents
        "Strateg": "Szeroki kontekst, cele długoterminowe",
        "Analityk": "Za i przeciw, analiza ryzyka", 
        "Praktyk": "Wykonalność, kroki implementacji",
        "Ekspert": "Głęboka wiedza domenowa",
        "Syntezator": "Łączy perspektywy w rekomendację",
        # Specialists
        "Social Media": "Facebook, Instagram, viral content",
        "LinkedIn": "B2B, networking, personal branding",
        "SEO": "Optymalizacja, keyword research, content SEO",
        "Blog Post": "Copywriting, storytelling, angażujące treści",
        "Branding": "Tożsamość marki, strategia, komunikacja"
    }
    
    return [
        AgentInfo(
            name=a.name,
            role=a.role,
            emoji=a.emoji,
            enabled=a.config.enabled,
            description=descriptions.get(a.name, a.config.personality[:50] if a.config.personality else "")
        )
        for a in agents
    ]


@app.post("/api/agents/{name}/toggle")
async def toggle_agent(name: str, request: AgentToggleRequest):
    """Enable/disable an agent"""
    success = agent_registry.toggle(name, request.enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {"name": name, "enabled": request.enabled}


@app.get("/api/stats")
async def get_stats():
    """Get knowledge base stats"""
    try:
        stats = get_ingestion_stats()
        return stats
    except Exception as e:
        return {"error": str(e), "total_vectors": 0}


@app.get("/api/providers")
async def get_providers():
    """Get available LLM providers and models"""
    return {
        "providers": AVAILABLE_PROVIDERS,
        "models": {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-5-nano", "gpt-5-mini", "gpt-5", "o1-mini"],
            "grok": ["grok-2", "grok-beta"],
            "grok": ["grok-2", "grok-beta"],
            "gemini": ["gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-exp"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
            "openrouter": ["google/gemini-3-pro-preview:free", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.1-70b-instruct", "google/gemini-2.0-flash-exp:free"]
        }
    }


@app.post("/api/deliberate", response_model=DeliberationResult)
async def deliberate(request: DeliberateRequest):
    """Run council deliberation"""
    
    # Build full query with attachment
    full_query = request.query
    if request.attachment_text:
        full_query = f"{request.query}\n\n---\n📎 ZAŁĄCZNIK:\n{request.attachment_text[:5000]}"
    
    # Add history context for chat mode
    if request.chat_mode and request.history:
        history_context = "\n\n---\n💬 POPRZEDNIA ROZMOWA:\n"
        for item in request.history[-3:]:
            history_context += f"Q: {item.get('query', '')[:200]}\n"
            if item.get('synthesis'):
                history_context += f"A: {item['synthesis'][:300]}...\n\n"
        full_query = history_context + "\n---\n📝 AKTUALNE PYTANIE:\n" + full_query
    
    # Create LLM provider
    if request.provider == "openai":
        llm = OpenAIProvider(model=request.model)
    elif request.provider == "grok":
        llm = GrokProvider(model=request.model)
    elif request.provider == "deepseek":
        llm = DeepSeekProvider(model=request.model)
    elif request.provider == "openrouter":
        llm = OpenRouterProvider(model=request.model)
    else:
        llm = GeminiProvider(model=request.model)
    
    # Create agents with selected provider
    agents = [
        Strategist(llm),
        Analyst(llm),
        Practitioner(llm),
        Expert(llm),
    ]
    synthesizer = Synthesizer(llm)
    
    # Register agents
    for agent in agents:
        agent_registry.register(agent)
    agent_registry.register(synthesizer)
    
    # Run deliberation
    council = Council(use_knowledge_base=request.use_knowledge_base)
    result = await council.deliberate(full_query)
    
    # Format response with token usage
    agent_responses = [
        AgentResponseData(
            agent_name=r.agent_name,
            role=r.role,
            content=r.content,
            provider_used=r.provider_used,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            model=r.model
        )
        for r in result.agent_responses
    ]
    
    synthesis = None
    if result.synthesis:
        synthesis = AgentResponseData(
            agent_name=result.synthesis.agent_name,
            role=result.synthesis.role,
            content=result.synthesis.content,
            provider_used=result.synthesis.provider_used,
            prompt_tokens=result.synthesis.prompt_tokens,
            completion_tokens=result.synthesis.completion_tokens,
            total_tokens=result.synthesis.total_tokens,
            model=result.synthesis.model
        )
    
    sources = [
        SourceData(
            title=s.get("title", "Unknown"),
            category=s.get("category", ""),
            max_score=s.get("max_score", 0),
            emoji=get_category_emoji(s.get("category", ""))
        )
        for s in result.sources[:5]
    ]
    
    # Build usage data from orchestrator's UsageStats
    usage = UsageData(
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        total_cost=result.usage.total_cost
    )
    
    return DeliberationResult(
        query=result.query,
        timestamp=result.timestamp,
        agent_responses=agent_responses,
        synthesis=synthesis,
        sources=sources,
        total_agents=result.total_agents,
        usage=usage
    )


@app.post("/api/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Import PDF to knowledge base"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    
    # Save temp file
    temp_path = Path("/tmp") / file.filename
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Ingest
    try:
        result = ingest_pdf(str(temp_path))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        temp_path.unlink(missing_ok=True)


@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str, format: str = "markdown"):
    """
    Export session to Markdown, HTML, or PDF
    
    Args:
        session_id: UUID of the session
        format: 'markdown', 'html', or 'pdf'
    """
    from src.storage import session_history, export_to_markdown, export_to_html, export_to_pdf
    
    # Load session
    session = session_history.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Format date for filename
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(session.metadata.timestamp)
        date_str = dt.strftime("%Y%m%d_%H%M")
    except:
        date_str = "export"
    
    filename_base = f"narada_{date_str}"
    
    if format == "markdown" or format == "md":
        content = export_to_markdown(session)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.md"}
        )
    
    elif format == "html":
        content = export_to_html(session)
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.html"}
        )
    
    elif format == "pdf":
        pdf_bytes = export_to_pdf(session)
        if pdf_bytes:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"}
            )
        else:
            # Fallback to HTML if PDF generation fails
            content = export_to_html(session)
            return Response(
                content=content,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename={filename_base}.html"}
            )
    
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'markdown', 'html', or 'pdf'")


@app.get("/api/deliberate/stream")
async def deliberate_stream(
    query: str,
    provider: str = "openai",
    model: str = "gpt-4o",
    use_knowledge_base: bool = True
):
    """
    Stream council deliberation via Server-Sent Events.
    Each agent's response is streamed token by token.
    """
    
    async def event_generator():
        try:
            # Create LLM provider
            # Create LLM provider
            if provider == "openai":
                llm = OpenAIProvider(model=model)
            elif provider == "grok":
                llm = GrokProvider(model=model)
            elif provider == "deepseek":
                llm = DeepSeekProvider(model=model)
            elif provider == "openrouter":
                llm = OpenRouterProvider(model=model)
            else:
                llm = GeminiProvider(model=model)
            
            # Create agents
            agents = [
                Strategist(llm),
                Analyst(llm),
                Practitioner(llm),
                Expert(llm),
            ]
            synthesizer = Synthesizer(llm)
            
            # Get context from knowledge base
            context = []
            sources = []
            if use_knowledge_base:
                try:
                    chunks = query_knowledge(query, top_k=5)
                    context = [c["text"] for c in chunks]
                    sources = format_sources_for_display(chunks)
                except Exception as e:
                    print(f"KB error: {e}")
            
            # Send sources info
            yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
            
            # Stream each agent sequentially
            all_responses = []
            for agent in agents:
                # Signal agent start
                yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role})}\n\n"
                
                full_response = ""
                async for token in agent.analyze_stream(query, context):
                    full_response += token
                    yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
                
                # Store response for synthesis
                all_responses.append({
                    'agent_name': f"{agent.emoji} {agent.name}",
                    'role': agent.role,
                    'content': full_response
                })
                
                # Signal agent done
                yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name})}\n\n"
            
            # Convert to mock AgentResponse objects for synthesizer
            from src.agents.base import AgentResponse
            mock_responses = [
                AgentResponse(
                    agent_name=r['agent_name'],
                    role=r['role'],
                    perspective="",
                    content=r['content'],
                    provider_used=llm.get_name()
                )
                for r in all_responses
            ]
            
            # Stream synthesis
            yield f"data: {json.dumps({'event': 'synthesis_start', 'agent': 'Syntezator', 'emoji': '🔮', 'role': 'Synthesizer'})}\n\n"
            
            synthesis_content = ""
            async for token in synthesizer.synthesize_stream(query, context, mock_responses):
                synthesis_content += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': 'Syntezator', 'content': token})}\n\n"
            
            yield f"data: {json.dumps({'event': 'synthesis_done', 'agent': 'Syntezator'})}\n\n"
            
            # Final complete event
            yield f"data: {json.dumps({'event': 'complete', 'total_agents': len(agents) + 1})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/debate/stream")
async def debate_stream(
    query: str,
    max_rounds: int = 3,
    provider: str = "openai",
    model: str = "gpt-4o",
    use_knowledge_base: bool = True
):
    """
    Run multi-round agent debate via Server-Sent Events.
    
    Rounds:
    1. Initial positions - each agent presents their stance
    2. Reactions - agents comment on each other
    3. Consensus - synthesizer identifies agreements/disagreements
    """
    
    # Create LLM provider
    if provider == "openai":
        llm = OpenAIProvider(model=model)
    elif provider == "grok":
        llm = GrokProvider(model=model)
    elif provider == "deepseek":
        llm = DeepSeekProvider(model=model)
    elif provider == "openrouter":
        llm = OpenRouterProvider(model=model)
    else:
        llm = GeminiProvider(model=model)
    
    # Create debate orchestrator
    orchestrator = DebateOrchestrator(use_knowledge_base=use_knowledge_base)
    
    return StreamingResponse(
        orchestrator.run_debate_stream(query, max_rounds=max_rounds, llm=llm),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ========== HISTORICAL COUNCIL API ==========
from src.agents.historical_agents import (
    HISTORICAL_GROUPS, 
    HISTORICAL_AGENTS_INFO, 
    list_available_historical_agents
)
from src.council.historical_council import HistoricalCouncil


@app.get("/api/historical/agents")
async def get_historical_agents():
    """Get available historical figures grouped by category"""
    agents = list_available_historical_agents()
    
    # Group by category
    grouped = {}
    for aid, info in agents.items():
        group = info["group"]
        if group not in grouped:
            grouped[group] = {
                "name": info["group_name"],
                "emoji": info["group_emoji"],
                "agents": []
            }
        grouped[group]["agents"].append({
            "id": aid,
            "name": info["name"],
            "emoji": info["emoji"],
            "role": info["role"],
            "personality": info["personality"]
        })
    
    return {
        "groups": HISTORICAL_GROUPS,
        "agents_by_group": grouped,
        "total_agents": len(agents)
    }


class HistoricalDeliberateRequest(BaseModel):
    query: str
    agent_ids: List[str] = []  # Empty = all agents
    provider: str = "openai"
    model: str = "gpt-4o"
    mode: str = "deliberate"  # "deliberate" or "debate"


@app.get("/api/historical/deliberate/stream")
async def historical_deliberate_stream(
    query: str,
    agent_ids: str = "",  # comma-separated
    provider: str = "openai",
    model: str = "gpt-4o",
    mode: str = "deliberate"
):
    """
    Stream Historical Council deliberation (Rada Mędrców).
    
    Args:
        query: User question
        agent_ids: Comma-separated agent IDs (e.g. "aristotle,buffett,musk")
        provider: LLM provider
        model: Model name
        mode: "deliberate" (simple) or "debate" (multi-round reactions)
    """
    
    # Parse agent IDs
    ids = [a.strip() for a in agent_ids.split(",") if a.strip()] if agent_ids else None
    
    # Create LLM provider
    # Create LLM provider
    from src.llm_providers import DeepSeekProvider
    if provider == "openai":
        llm = OpenAIProvider(model=model)
    elif provider == "grok":
        llm = GrokProvider(model=model)
    elif provider == "deepseek":
        llm = DeepSeekProvider(model=model)
    elif provider == "openrouter":
        llm = OpenRouterProvider(model=model)
    else:
        llm = GeminiProvider(model=model)
    
    # Create Historical Council
    council = HistoricalCouncil(use_knowledge_base=True)
    
    # Choose mode
    if mode == "debate":
        stream = council.debate_stream(query, agent_ids=ids, llm=llm)
    else:
        stream = council.deliberate_stream(query, agent_ids=ids, llm=llm)
    
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ========== COUNCIL MODES API ==========
from src.council.modes import COUNCIL_MODES, get_mode, list_modes


@app.get("/api/council/modes")
async def get_council_modes():
    """Get available council modes"""
    return {
        "modes": list_modes()
    }


@app.get("/api/council/mode/stream")
async def council_mode_stream(
    mode: str,
    query: str,
    provider: str = "openai",
    model: str = "gpt-4o"
):
    """
    Stream council mode deliberation.
    
    Args:
        mode: Mode ID (deep_dive, speed_round, devils_advocate, swot, red_team)
        query: User question
        provider: LLM provider
        model: Model name
    """
    mode_instance = get_mode(mode)
    if not mode_instance:
        return {"error": f"Unknown mode: {mode}"}
    
    # Create LLM provider
    # Create LLM provider
    from src.llm_providers import DeepSeekProvider
    if provider == "openai":
        llm = OpenAIProvider(model=model)
    elif provider == "grok":
        llm = GrokProvider(model=model)
    elif provider == "deepseek":
        llm = DeepSeekProvider(model=model)
    elif provider == "openrouter":
        llm = OpenRouterProvider(model=model)
    else:
        llm = GeminiProvider(model=model)
    
    return StreamingResponse(
        mode_instance.run_stream(query, llm),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ========== CUSTOM AGENTS API ==========
@app.get("/api/agents/custom")
async def list_custom_agents():
    """List all custom agents"""
    agents = agent_storage.load_all()
    return [get_custom_agent_info(a) for a in agents]


@app.post("/api/agents/custom")
async def create_custom_agent_endpoint(request: CustomAgentRequest):
    """Create a new custom agent"""
    config = CustomAgentConfig(
        name=request.name,
        emoji=request.emoji,
        role=request.role,
        persona=request.persona,
        system_prompt=request.system_prompt,
        template_id=request.template_id,
        tools=request.tools,
        context_limit=request.context_limit,
        memory_type=request.memory_type,
        enabled=request.enabled
    )
    
    agent_id = agent_storage.save(config)
    return {"id": agent_id, "message": "Agent created", "agent": config.to_dict()}


@app.get("/api/agents/custom/{agent_id}")
async def get_custom_agent(agent_id: str):
    """Get a specific custom agent"""
    config = agent_storage.get(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    return config.to_dict()


@app.put("/api/agents/custom/{agent_id}")
async def update_custom_agent(agent_id: str, request: CustomAgentRequest):
    """Update a custom agent"""
    existing = agent_storage.get(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    updates = {
        "name": request.name,
        "emoji": request.emoji,
        "role": request.role,
        "persona": request.persona,
        "system_prompt": request.system_prompt,
        "template_id": request.template_id,
        "tools": request.tools,
        "context_limit": request.context_limit,
        "memory_type": request.memory_type,
        "enabled": request.enabled
    }
    
    updated = agent_storage.update(agent_id, updates)
    return {"message": "Agent updated", "agent": updated.to_dict()}


@app.delete("/api/agents/custom/{agent_id}")
async def delete_custom_agent(agent_id: str):
    """Delete a custom agent"""
    if not agent_storage.delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted"}


@app.post("/api/agents/custom/{agent_id}/toggle")
async def toggle_custom_agent(agent_id: str):
    """Toggle agent enabled status"""
    new_status = agent_storage.toggle_enabled(agent_id)
    if new_status is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"enabled": new_status}


# ========== TEMPLATES API ==========
@app.get("/api/agents/templates")
async def list_templates():
    """List all prompt templates"""
    return get_all_templates()


@app.get("/api/agents/templates/{template_id}")
async def get_template_endpoint(template_id: str):
    """Get a specific template"""
    template = get_template(template_id)
    return template


@app.get("/api/agents/templates-by-category")
async def list_templates_by_category():
    """List templates grouped by category"""
    return get_templates_by_category()


# ========== AGENT TEST API ==========
@app.post("/api/agents/test")
async def test_custom_agent(request: AgentTestRequest):
    """Test a custom agent configuration with a query"""
    # Create temp config
    config = CustomAgentConfig(
        name=request.config.name,
        emoji=request.config.emoji,
        role=request.config.role,
        persona=request.config.persona,
        system_prompt=request.config.system_prompt,
        tools=request.config.tools,
        context_limit=request.config.context_limit
    )
    
    # Create provider
    # Create provider
    if request.provider == "openai":
        llm = OpenAIProvider(model=request.model)
    elif request.provider == "grok":
        llm = GrokProvider(model=request.model)
    elif request.provider == "deepseek":
        llm = DeepSeekProvider(model=request.model)
    elif request.provider == "openrouter":
        llm = OpenRouterProvider(model=request.model)
    else:
        llm = GeminiProvider(model=request.model)
    
    # Create and test agent
    agent = CustomAgent(config, llm)
    
    # Get context if knowledge base tool enabled
    context = []
    if "knowledge_base" in config.tools:
        try:
            chunks = query_knowledge(request.query, top_k=3)
            context = [c["text"] for c in chunks]
        except:
            pass
    
    # Run analysis
    response = await agent.analyze(request.query, context)
    
    return {
        "agent_name": response.agent_name,
        "role": response.role,
        "content": response.content,
        "provider_used": response.provider_used
    }


# ========== PLUGINS API ==========
@app.get("/api/plugins")
async def list_plugins():
    """List all available plugins"""
    pm = get_plugin_manager()
    return pm.list_all()


@app.get("/api/plugins/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get plugin details"""
    pm = get_plugin_manager()
    plugin = pm.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin.get_info()


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = 5
    use_tavily: bool = True  # False = use DuckDuckGo


@app.post("/api/plugins/web-search")
async def web_search(request: WebSearchRequest):
    """Execute web search"""
    pm = get_plugin_manager()
    
    if request.use_tavily:
        plugin = pm.get("tavily")
        if not plugin or not plugin.is_configured():
            # Fallback to DuckDuckGo
            plugin = pm.get("duckduckgo")
    else:
        plugin = pm.get("duckduckgo")
    
    if not plugin:
        raise HTTPException(status_code=500, detail="No search plugin available")
    
    result = await plugin.execute(query=request.query, max_results=request.max_results)
    return result.to_dict()


class URLAnalyzeRequest(BaseModel):
    url: str
    extract_links: bool = False
    summarize: bool = False


@app.post("/api/plugins/analyze-url")
async def analyze_url(request: URLAnalyzeRequest):
    """Analyze a URL"""
    pm = get_plugin_manager()
    plugin = pm.get("url_analyzer")
    
    if not plugin:
        raise HTTPException(status_code=500, detail="URL Analyzer not available")
    
    if request.summarize:
        # Use LLM for summary
        llm = OpenAIProvider(model="gpt-4o-mini")
        result = await plugin.summarize(request.url, llm)
    else:
        result = await plugin.execute(
            url=request.url, 
            extract_links=request.extract_links
        )
    
    return result.to_dict()


# --- Wikipedia ---
class WikipediaRequest(BaseModel):
    query: str
    lang: str = "pl"
    summary_only: bool = True


@app.post("/api/plugins/wikipedia")
async def wikipedia_search(request: WikipediaRequest):
    pm = get_plugin_manager()
    plugin = pm.get("wikipedia")
    result = await plugin.execute(query=request.query, lang=request.lang, summary_only=request.summary_only)
    return result.to_dict()


# --- Weather ---
class WeatherRequest(BaseModel):
    city: str
    forecast_days: int = 3


@app.post("/api/plugins/weather")
async def get_weather(request: WeatherRequest):
    pm = get_plugin_manager()
    plugin = pm.get("weather")
    result = await plugin.execute(city=request.city, forecast_days=request.forecast_days)
    return result.to_dict()


# --- Stocks ---
class StockRequest(BaseModel):
    symbol: str
    period: str = "1d"


@app.post("/api/plugins/stocks")
async def get_stock(request: StockRequest):
    pm = get_plugin_manager()
    plugin = pm.get("stocks")
    result = await plugin.execute(symbol=request.symbol, period=request.period)
    return result.to_dict()


# --- Calculator ---
class CalculatorRequest(BaseModel):
    expression: str


@app.post("/api/plugins/calculator")
async def calculate(request: CalculatorRequest):
    pm = get_plugin_manager()
    plugin = pm.get("calculator")
    result = await plugin.execute(expression=request.expression)
    return result.to_dict()


# --- Generic Plugin Execute ---
class GenericPluginRequest(BaseModel):
    plugin_id: str
    params: Dict[str, Any] = {}


@app.post("/api/plugins/execute")
async def execute_plugin(request: GenericPluginRequest):
    """Execute any plugin by ID with params"""
    pm = get_plugin_manager()
    plugin = pm.get(request.plugin_id)
    
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {request.plugin_id}")
    
    result = await plugin.execute(**request.params)
    return result.to_dict()


# ========== SEO ARTICLE GENERATOR API ==========
from src.seo import (
    ArticleGenerator, ArticleResult,
    BrandInfo, BrandInfoManager,
    AhrefsImporter, AhrefsData,
    SERPAnalyzer
)
from src.seo.article_storage import ArticleStorage


class SEOGenerateRequest(BaseModel):
    topic: str
    target_url: str = ""
    keywords: List[str] = []
    ahrefs_data: str = ""
    min_words: int = 1500
    include_brand_info: bool = True
    analyze_serp: bool = True
    perplexity_model: str = "sonar-pro"
    provider: str = "openai"
    model: str = "gpt-4o"
    force_generate: bool = False


class BrandInfoRequest(BaseModel):
    name: str = ""
    description: str = ""
    value_proposition: str = ""
    tone_of_voice: str = "professional"
    key_products: List[str] = []
    target_audience: str = ""
    unique_selling_points: List[str] = []
    preferred_cta: str = ""
    do_not_mention: List[str] = []


@app.post("/api/seo/generate")
async def generate_seo_article(request: SEOGenerateRequest):
    """
    Generate SEO-optimized article
    
    Full pipeline:
    1. Check for similar existing articles
    2. Parse Ahrefs data if provided
    3. Analyze SERP competition
    4. Research via Perplexity
    5. Generate article with brand context
    6. Store in Pinecone
    """
    # Create LLM provider
    from src.llm_providers import DeepSeekProvider, PerplexityProvider
    
    if request.provider == "openai":
        llm = OpenAIProvider(model=request.model)
    elif request.provider == "grok":
        llm = GrokProvider(model=request.model)
    elif request.provider == "deepseek":
        llm = DeepSeekProvider(model=request.model)
    elif request.provider == "perplexity":
        llm = PerplexityProvider(model=request.model)
    else:
        llm = GeminiProvider(model=request.model)
    
    generator = ArticleGenerator()
    
    result = await generator.generate(
        topic=request.topic,
        target_url=request.target_url,
        keywords=request.keywords,
        ahrefs_data=request.ahrefs_data,
        min_words=request.min_words,
        include_brand_info=request.include_brand_info,
        analyze_serp=request.analyze_serp,
        perplexity_model=request.perplexity_model if request.perplexity_model else None,
        main_llm_provider=llm,
        force_generate=request.force_generate
    )
    
    if result.success:
        return {
            "success": True,
            "article_id": result.article.id,
            "title": result.article.title,
            "word_count": result.article.word_count,
            "article_html": result.article_html,
            "article_markdown": result.article_markdown,
            "usage": result.usage,
            # SEO Structure Features
            "schema_json_ld": result.schema_json_ld,
            "schema_html_script": result.schema_html_script,
            "table_of_contents": result.table_of_contents,
            "featured_snippet_suggestions": result.featured_snippet_suggestions
        }
    else:
        return {
            "success": False,
            "error": result.error,
            "similar_exists": result.similar_exists,
            "similar_articles": [
                {"id": a.id, "title": a.title, "similarity": a.similarity_score}
                for a in result.similar_articles
            ] if result.similar_articles else []
        }


@app.post("/api/seo/analyze-url")
async def seo_analyze_target_url(url: str):
    """Analyze target website theme and structure"""
    from src.plugins.url_analyzer import URLAnalyzerPlugin
    
    analyzer = URLAnalyzerPlugin()
    result = await analyzer.execute(url, extract_links=True, max_content_length=5000)
    
    if result.success:
        return {
            "success": True,
            "url": url,
            "title": result.data.get("title", ""),
            "description": result.data.get("description", ""),
            "content_preview": result.data.get("content", "")[:1000],
            "links": result.data.get("links", [])[:10]
        }
    else:
        return {"success": False, "error": result.error}


@app.post("/api/seo/serp-analysis")
async def run_serp_analysis(keyword: str, max_results: int = 5):
    """Analyze SERP competition for keyword"""
    analyzer = SERPAnalyzer()
    result = await analyzer.analyze(keyword, max_competitors=max_results)
    
    return {
        "keyword": result.keyword,
        "competitors": [
            {
                "position": c.position,
                "title": c.title,
                "url": c.url,
                "domain": c.domain,
                "snippet": c.snippet
            }
            for c in result.competitors
        ],
        "common_themes": result.common_themes,
        "content_gaps": result.content_gaps,
        "suggested_angles": result.suggested_angles,
        "avg_word_count": result.avg_word_count
    }


class DeepCompetitorRequest(BaseModel):
    keyword: str
    competitor_urls: List[str]
    our_content: str = ""


@app.post("/api/seo/competitor-analysis")
async def run_deep_competitor_analysis(request: DeepCompetitorRequest):
    """
    Deep competitor analysis: heading structure, word count, topic gaps
    
    Features:
    - Scrapes H1-H6 structure from each URL
    - Calculates word count statistics
    - Identifies common headings across competitors
    - NLP topic extraction and gap analysis
    """
    from src.seo import CompetitorAnalyzer
    
    analyzer = CompetitorAnalyzer()
    result = await analyzer.analyze_competitors(
        keyword=request.keyword,
        competitor_urls=request.competitor_urls,
        our_content=request.our_content
    )
    
    # Generate recommendations
    recommendations = analyzer.generate_recommendations(result)
    
    return {
        "keyword": result.keyword,
        "analyzed_count": len(result.competitors),
        "competitors": [
            {
                "url": c.url,
                "title": c.title,
                "word_count": c.word_count,
                "headings": [{"level": h.level, "text": h.text} for h in c.headings[:20]],
                "main_topics": c.main_topics[:10],
                "error": c.fetch_error
            }
            for c in result.competitors
        ],
        "word_count_stats": {
            "avg": result.avg_word_count,
            "min": result.min_word_count,
            "max": result.max_word_count,
            "recommended": result.recommended_word_count
        },
        "common_headings": result.common_headings[:15],
        "heading_patterns": result.common_heading_patterns,
        "all_topics": result.all_topics[:20],
        "missing_topics": result.missing_topics,
        "topic_frequency": result.topic_frequency,
        "recommendations": recommendations,
        "context_for_llm": result.to_context_string()
    }


class AhrefsImportRequest(BaseModel):
    text_content: str = ""


@app.post("/api/seo/import-ahrefs")
async def import_ahrefs_data(
    request: AhrefsImportRequest = None,
    file: UploadFile = File(None)
):
    """Import keywords data from Ahrefs export (CSV or pasted text)"""
    importer = AhrefsImporter()
    
    content = ""
    source = "text"
    
    if file:
        content = (await file.read()).decode("utf-8")
        source = "csv" if file.filename.endswith(".csv") else "text"
    elif request and request.text_content:
        content = request.text_content
    else:
        return {"success": False, "error": "No data provided"}
    
    if source == "csv":
        result = importer.parse_csv(content)
    else:
        result = importer.parse_text(content)
    
    return {
        "success": True,
        "source": result.source,
        "keywords_count": len(result.keywords),
        "keywords": [
            {
                "keyword": kw.keyword,
                "volume": kw.volume,
                "difficulty": kw.difficulty,
                "cpc": kw.cpc
            }
            for kw in result.keywords[:50]  # Max 50 for response
        ],
        "primary_keywords": result.get_primary_keywords(),
        "low_difficulty_keywords": result.get_low_difficulty()
    }


@app.get("/api/seo/brand-info")
async def get_brand_info():
    """Get configured brand information"""
    manager = BrandInfoManager()
    info = manager.load()
    return info.to_dict()


@app.put("/api/seo/brand-info")
async def update_brand_info(request: BrandInfoRequest):
    """Update brand/company information"""
    manager = BrandInfoManager()
    
    info = BrandInfo(
        name=request.name,
        description=request.description,
        value_proposition=request.value_proposition,
        tone_of_voice=request.tone_of_voice,
        key_products=request.key_products,
        target_audience=request.target_audience,
        unique_selling_points=request.unique_selling_points,
        preferred_cta=request.preferred_cta,
        do_not_mention=request.do_not_mention
    )
    
    success = manager.save(info)
    
    return {
        "success": success,
        "brand_info": info.to_dict()
    }


@app.get("/api/seo/articles")
async def list_seo_articles(limit: int = 50):
    """List generated articles from storage"""
    storage = ArticleStorage()
    
    try:
        articles = await storage.list_all(limit=limit)
        return {
            "success": True,
            "count": len(articles),
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "topic": a.topic,
                    "target_url": a.target_url,
                    "word_count": a.word_count,
                    "created_at": a.created_at
                }
                for a in articles
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e), "articles": []}


@app.get("/api/seo/articles/{article_id}")
async def get_seo_article(article_id: str):
    """Get specific article by ID"""
    storage = ArticleStorage()
    
    article = await storage.get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {
        "id": article.id,
        "title": article.title,
        "topic": article.topic,
        "target_url": article.target_url,
        "keywords": article.keywords,
        "word_count": article.word_count,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "content_markdown": article.content,
        "content_html": article.content_html
    }


class ArticleImproveRequest(BaseModel):
    instructions: str
    provider: str = "openai"
    model: str = "gpt-4o"


@app.post("/api/seo/articles/{article_id}/improve")
async def improve_seo_article(article_id: str, request: ArticleImproveRequest):
    """Improve existing article with new instructions"""
    from src.llm_providers import DeepSeekProvider
    
    # Create LLM provider
    if request.provider == "openai":
        llm = OpenAIProvider(model=request.model)
    elif request.provider == "grok":
        llm = GrokProvider(model=request.model)
    elif request.provider == "deepseek":
        llm = DeepSeekProvider(model=request.model)
    elif request.provider == "openrouter":
        llm = OpenRouterProvider(model=request.model)
    else:
        llm = GeminiProvider(model=request.model)
    
    generator = ArticleGenerator()
    result = await generator.improve(article_id, request.instructions, llm)
    
    if result.success:
        return {
            "success": True,
            "article_id": result.article.id,
            "title": result.article.title,
            "word_count": result.article.word_count,
            "article_html": result.article_html,
            "article_markdown": result.article_markdown,
            "usage": result.usage
        }
    else:
        return {"success": False, "error": result.error}


@app.delete("/api/seo/articles/{article_id}")
async def delete_seo_article(article_id: str):
    """Delete an article"""
    storage = ArticleStorage()
    success = await storage.delete(article_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {"success": True, "message": "Article deleted"}


# ========== RUN ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
