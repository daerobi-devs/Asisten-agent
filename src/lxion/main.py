import asyncio
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

import httpx
from lxion.core.config import settings, update_env_file
from lxion.core.logger import logger
from lxion.memory.db import init_db
from lxion.memory.workspace import workspace
from lxion.llm.router_client import NineRouterClient
from lxion.llm.token_tracker import tracker
from lxion.tools.registry import registry
from lxion.core.agent import Agent
from lxion.core.context import SessionContext
from lxion.scheduler.cron_manager import cron_manager, JobType
from lxion.kanban.task_store import kanban_store, TaskStatus, TaskPriority
from lxion.channels.telegram_bot import telegram_gateway
from lxion.channels.discord_bot import discord_gateway
from lxion.channels.bus import message_bus, InboundMessage, ChannelType
from lxion.agents.profile_store import profile_store, AgentProfile
from lxion.tools.installer.skill_manager import skill_manager
from lxion.channels.whatsapp_manager import whatsapp_manager, WhatsAppMode
from lxion.llm.multi_provider import multi_provider_router
from lxion.security.rate_limiter import rate_limiter

STATIC_DIR = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.AGENT_NAME} Core Engine (v0.3.0)...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Error during init_db: {e}", exc_info=True)
    
    # Start Cron Engine
    try:
        cron_manager.start()
    except Exception as e:
        logger.error(f"Error starting cron_manager: {e}", exc_info=True)

    # Start Telegram Bot if configured (from settings or lxion_core profile)
    try:
        tg_token = settings.TELEGRAM_BOT_TOKEN
        if not tg_token:
            p = profile_store.get_profile("lxion_core")
            if p and p.channel_bindings.get("telegram_token"):
                tg_token = p.channel_bindings.get("telegram_token")
                settings.TELEGRAM_BOT_TOKEN = tg_token
        if tg_token:
            try:
                await telegram_gateway.start(tg_token)
            except Exception as e:
                logger.warning(f"Could not start Telegram Bot: {e}")
    except Exception as e:
        logger.error(f"Error initializing Telegram bot: {e}", exc_info=True)

    # Start Discord Bot if configured
    try:
        discord_token = settings.DISCORD_BOT_TOKEN
        if not discord_token:
            p = profile_store.get_profile("lxion_core")
            if p and p.channel_bindings.get("discord_token"):
                discord_token = p.channel_bindings.get("discord_token")
                settings.DISCORD_BOT_TOKEN = discord_token
        if discord_token:
            try:
                await discord_gateway.start(token=discord_token)
            except Exception as e:
                logger.warning(f"Could not start Discord Bot: {e}")
    except Exception as e:
        logger.error(f"Error initializing Discord bot: {e}", exc_info=True)

    yield

    # Graceful shutdown
    try:
        cron_manager.stop()
    except Exception:
        pass
    try:
        await telegram_gateway.stop()
        logger.info("✓ Telegram Bot stopped.")
    except Exception:
        pass
    if discord_gateway.is_running:
        try:
            await discord_gateway.stop()
            logger.info("✓ Discord Gateway stopped.")
        except Exception:
            pass
    logger.info(f"🛑 Stopped {settings.AGENT_NAME} Core Engine.")

app = FastAPI(
    title=f"{settings.AGENT_NAME} Agent API",
    version="0.3.0",
    description="Autonomous Full-Featured Agentic Assistant Engine",
    lifespan=lifespan
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>LXION Agent Core Active. Dashboard loading...</h1>")

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = None
    agent_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    token_stats: Dict[str, Any]

class KeyUpdateRequest(BaseModel):
    nine_router_key: Optional[str] = None
    nine_router_url: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    coolify_url: Optional[str] = None
    coolify_token: Optional[str] = None
    companion_token: Optional[str] = None
    telegram_token: Optional[str] = None
    discord_token: Optional[str] = None

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"
    status: Optional[str] = "todo"

class UpdateTaskStatusRequest(BaseModel):
    task_id: str
    status: str

class CreateJobRequest(BaseModel):
    name: str
    schedule_type: str = "interval"
    schedule_value: str
    job_type: str = "direct_tool"
    target: str
    channel: Optional[str] = "none"
    agent_id: Optional[str] = "lxion_core"
    parameters: Optional[Dict[str, Any]] = None

class WorkspaceFileWriteRequest(BaseModel):
    path: str
    content: str

class WorkspaceFolderCreateRequest(BaseModel):
    path: str

class WorkspaceZipRequest(BaseModel):
    sources: List[str]
    zip_name: Optional[str] = None

class CompanionExecRequest(BaseModel):
    command: str
    timeout_seconds: int = 30

class TelegramStartRequest(BaseModel):
    token: Optional[str] = None

class DiscordStartRequest(BaseModel):
    token: Optional[str] = None
    allowed_channels: Optional[List[int]] = None

class WhatsAppModeRequest(BaseModel):
    mode: str
    trigger_prefix: Optional[str] = "!ai"

class WhatsAppPairRequest(BaseModel):
    phone: str
    mode: Optional[str] = "self_chat"

class WhatsAppPairCodeRequest(BaseModel):
    phone: str

router_client = NineRouterClient()
agent_engine = Agent(router_client=router_client)
active_sessions: Dict[str, SessionContext] = {}

async def core_agent_channel_handler(inbound: InboundMessage) -> str:
    session_id = inbound.session_id or f"{inbound.channel.value}_{inbound.sender_id}"
    if session_id not in active_sessions:
        active_sessions[session_id] = SessionContext(session_id=session_id)
    ctx = active_sessions[session_id]

    allowed, reason = rate_limiter.check_allowed(estimated_tokens=300)
    if not allowed:
        return f"⚠️ Batas rate limit terlampaui: {reason}. Mohon tunggu sebentar."

    try:
        # Resolve target profile: WhatsApp is strictly locked to Primary Agent
        target_profile = None
        if inbound.channel == ChannelType.WHATSAPP:
            target_profile = profile_store.get_profile("lxion_core")
        else:
            # Check for dedicated channel binding in sub-agents
            for p in profile_store.list_profiles():
                if inbound.channel == ChannelType.DISCORD and p.channel_bindings.get("discord_token"):
                    target_profile = p
                    break
                elif inbound.channel == ChannelType.TELEGRAM and p.channel_bindings.get("telegram_token"):
                    target_profile = p
                    break
            if not target_profile:
                target_profile = profile_store.get_profile("lxion_core")

        reply = await agent_engine.run(user_prompt=inbound.text, context=ctx, profile=target_profile)
        rate_limiter.record_request(tokens=500)
        return reply
    except Exception as e:
        logger.error(f"Error handling channel message from {inbound.channel.value}: {e}")
        return f"⚠️ Terjadi kendala saat memproses: {e}"

message_bus.set_agent_handler(core_agent_channel_handler)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": settings.AGENT_NAME,
        "gateway": settings.NINE_ROUTER_BASE_URL,
        "environment": settings.ENVIRONMENT,
        "active_tools": len(registry.get_all_tools()),
        "active_cron_jobs": len(cron_manager.list_jobs())
    }

@app.get("/api/models")
async def get_models():
    models = await router_client.list_models()
    return {"models": models}

@app.get("/api/tools")
async def get_tools():
    tools = [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in registry.get_all_tools()
    ]
    return {"tools": tools}

@app.get("/api/stats")
async def get_stats():
    return tracker.get_summary()

@app.get("/api/kanban")
async def get_kanban_board():
    return kanban_store.get_board()

@app.get("/api/scheduler/jobs")
async def get_scheduler_jobs():
    return {
        "jobs": cron_manager.list_jobs(),
        "history": cron_manager.get_history(20)
    }

@app.get("/api/workspace/files")
async def get_workspace_files(include_system: bool = False):
    files = workspace.list_files(include_system=include_system)
    tree = workspace.get_tree(include_system=include_system)
    return {"files": files, "tree": tree}

@app.get("/api/workspace/file")
async def get_workspace_file_content(path: str):
    ws = settings.WORKSPACE_DIR.resolve()
    target = (ws / path).resolve()
    if not str(target).startswith(str(ws)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companion/status")
async def get_companion_status():
    import httpx
    url = f"http://{settings.COMPANION_HOST}:{settings.COMPANION_PORT}/health"
    try:
        async with httpx.AsyncClient(timeout=2.0) as http_client:
            res = await http_client.get(url, headers={"Authorization": f"Bearer {settings.COMPANION_AUTH_TOKEN}"})
            if res.status_code == 200:
                return {"online": True, "details": res.json()}
    except Exception:
        pass
@app.get("/api/channels/status")
async def get_channels_status():
    return {
        "telegram": telegram_gateway.get_status(),
        "whatsapp": whatsapp_manager.get_status(),
        "discord": discord_gateway.get_status()
    }

@app.post("/api/channels/telegram/start")
async def start_telegram_bot_endpoint(req: TelegramStartRequest):
    token = req.token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        p = profile_store.get_profile("lxion_core")
        if p and p.channel_bindings.get("telegram_token"):
            token = p.channel_bindings.get("telegram_token")
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    settings.TELEGRAM_BOT_TOKEN = token
    update_env_file({"TELEGRAM_BOT_TOKEN": token})
    try:
        ok = await telegram_gateway.start(token=token)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to start Telegram Bot polling")
        return {"status": "ok", "message": "Telegram bot started", "telegram": telegram_gateway.get_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Telegram bot: {e}")

@app.post("/api/channels/telegram/stop")
async def stop_telegram_bot_endpoint():
    await telegram_gateway.stop()
    return {"status": "ok", "message": "Telegram bot stopped", "telegram": telegram_gateway.get_status()}

@app.post("/api/channels/discord/start")
async def start_discord_bot(req: DiscordStartRequest):
    token = req.token or settings.DISCORD_BOT_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="Discord bot token is required")
    if req.token:
        settings.DISCORD_BOT_TOKEN = req.token
        update_env_file({"DISCORD_BOT_TOKEN": req.token})
    try:
        await discord_gateway.start(token=token, allowed_channels=req.allowed_channels)
        return {"status": "ok", "message": "Discord bot started", "discord": discord_gateway.get_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Discord bot: {e}")

@app.post("/api/channels/discord/stop")
async def stop_discord_bot():
    await discord_gateway.stop()
    return {"status": "ok", "message": "Discord bot stopped", "discord": discord_gateway.get_status()}

@app.post("/api/channels/whatsapp/qr")
async def get_whatsapp_qr():
    res = whatsapp_manager.generate_qr_code()
    return res

@app.post("/api/channels/whatsapp/pair")
async def pair_whatsapp_device(req: WhatsAppPairRequest):
    mode = WhatsAppMode(req.mode) if req.mode else WhatsAppMode.SELF_CHAT
    res = whatsapp_manager.confirm_pairing(phone_number=req.phone, mode=mode)
    return {"status": "ok", "whatsapp": res}

@app.post("/api/channels/whatsapp/mode")
async def set_whatsapp_mode(req: WhatsAppModeRequest):
    try:
        mode = WhatsAppMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}. Allowed: self_chat, bot")
    res = whatsapp_manager.set_mode(mode=mode, trigger_prefix=req.trigger_prefix)
    return {"status": "ok", "whatsapp": res}

@app.post("/api/channels/whatsapp/pair-code")
async def request_whatsapp_pairing_code(req: WhatsAppPairCodeRequest):
    try:
        data = whatsapp_manager.request_pairing_code(phone_number=req.phone)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/channels/whatsapp/disconnect")
async def disconnect_whatsapp():
    res = whatsapp_manager.disconnect()
    return {"status": "ok", "whatsapp": res}

@app.get("/api/settings/keys")
async def get_settings_keys():
    def mask_key(k: Optional[str]) -> str:
        if not k:
            return "Not Configured"
        if len(k) <= 8:
            return "••••••••"
        return k[:4] + "••••" + k[-4:]

    return {
        "nine_router": {
            "base_url": settings.NINE_ROUTER_BASE_URL,
            "api_key": mask_key(settings.NINE_ROUTER_API_KEY),
            "configured": bool(settings.NINE_ROUTER_API_KEY)
        },
        "coolify": {
            "base_url": settings.COOLIFY_BASE_URL,
            "api_token": mask_key(settings.COOLIFY_API_TOKEN),
            "configured": bool(settings.COOLIFY_API_TOKEN)
        },
        "companion": {
            "host": settings.COMPANION_HOST,
            "port": settings.COMPANION_PORT,
            "token": mask_key(settings.COMPANION_AUTH_TOKEN),
            "configured": bool(settings.COMPANION_AUTH_TOKEN)
        },
        "telegram": {
            "token": mask_key(settings.TELEGRAM_BOT_TOKEN),
            "configured": bool(settings.TELEGRAM_BOT_TOKEN)
        },
        "discord": {
            "token": mask_key(settings.DISCORD_BOT_TOKEN),
            "configured": bool(settings.DISCORD_BOT_TOKEN)
        }
    }

@app.get("/api/providers/status")
async def get_providers_status():
    return multi_provider_router.get_providers_status()

@app.get("/api/security/status")
async def get_security_status():
    return {
        "rate_limiter": rate_limiter.get_status(),
        "sandbox": "isolated_subprocess",
        "command_jail": "strict_whitelist"
    }

@app.post("/api/settings/keys")
async def update_settings_keys(req: KeyUpdateRequest):
    updates = {}
    if req.nine_router_key is not None and req.nine_router_key.strip():
        val = req.nine_router_key.strip()
        updates["NINE_ROUTER_API_KEY"] = val
        settings.NINE_ROUTER_API_KEY = val
        router_client.api_key = val
        multi_provider_router.primary.api_key = val
    if req.nine_router_url is not None and req.nine_router_url.strip():
        val = req.nine_router_url.strip().rstrip("/")
        updates["NINE_ROUTER_BASE_URL"] = val
        settings.NINE_ROUTER_BASE_URL = val
        router_client.base_url = val
        multi_provider_router.primary.base_url = val
    if req.openai_key is not None and req.openai_key.strip():
        val = req.openai_key.strip()
        updates["OPENAI_API_KEY"] = val
        settings.OPENAI_API_KEY = val
        multi_provider_router.openai.api_key = val
    if req.anthropic_key is not None and req.anthropic_key.strip():
        val = req.anthropic_key.strip()
        updates["ANTHROPIC_API_KEY"] = val
        settings.ANTHROPIC_API_KEY = val
        multi_provider_router.anthropic.api_key = val
    if req.coolify_url is not None and req.coolify_url.strip():
        val = req.coolify_url.strip()
        updates["COOLIFY_BASE_URL"] = val
        settings.COOLIFY_BASE_URL = val
    if req.coolify_token is not None and req.coolify_token.strip():
        val = req.coolify_token.strip()
        updates["COOLIFY_API_TOKEN"] = val
        settings.COOLIFY_API_TOKEN = val
    if req.companion_token is not None and req.companion_token.strip():
        val = req.companion_token.strip()
        updates["COMPANION_AUTH_TOKEN"] = val
        settings.COMPANION_AUTH_TOKEN = val
    if req.telegram_token is not None and req.telegram_token.strip():
        val = req.telegram_token.strip()
        updates["TELEGRAM_BOT_TOKEN"] = val
        settings.TELEGRAM_BOT_TOKEN = val
        asyncio.create_task(telegram_gateway.start(val))
    if req.discord_token is not None and req.discord_token.strip():
        val = req.discord_token.strip()
        updates["DISCORD_BOT_TOKEN"] = val
        settings.DISCORD_BOT_TOKEN = val
        discord_gateway.token = val

    if updates:
        update_env_file(updates)
        logger.info(f"✓ Updated runtime and .env settings keys: {list(updates.keys())}")
    return {"status": "ok", "updated_keys": list(updates.keys())}

@app.post("/api/kanban/task")
async def create_kanban_task(req: CreateTaskRequest):
    try:
        p_enum = TaskPriority(req.priority.lower()) if req.priority else TaskPriority.MEDIUM
    except ValueError:
        p_enum = TaskPriority.MEDIUM
    try:
        s_enum = TaskStatus(req.status.lower()) if req.status else TaskStatus.TODO
    except ValueError:
        s_enum = TaskStatus.TODO

    task = kanban_store.create_task(
        title=req.title,
        description=req.description or "",
        priority=p_enum,
        status=s_enum
    )
    return {"status": "ok", "task": task.model_dump()}

@app.post("/api/kanban/task/status")
async def update_task_status(req: UpdateTaskStatusRequest):
    try:
        s_enum = TaskStatus(req.status.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task status")
    task = kanban_store.update_task(task_id=req.task_id, status=s_enum)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.model_dump()}

@app.delete("/api/kanban/task/{task_id}")
async def delete_kanban_task(task_id: str):
    success = kanban_store.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "deleted": task_id}

@app.post("/api/scheduler/job")
async def create_scheduler_job(req: CreateJobRequest):
    job_id = f"job_{int(time.time())}"
    try:
        j_type = JobType(req.job_type)
    except ValueError:
        j_type = JobType.DIRECT_TOOL

    job_info = cron_manager.add_job(
        job_id=job_id,
        name=req.name,
        schedule_type=req.schedule_type,
        schedule_value=req.schedule_value,
        job_type=j_type,
        target=req.target,
        channel=req.channel or "none",
        agent_id=req.agent_id or "lxion_core",
        parameters=req.parameters or {}
    )
    return {"status": "ok", "job": job_info}

@app.delete("/api/scheduler/job/{job_id}")
async def delete_scheduler_job(job_id: str):
    success = cron_manager.remove_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "ok", "deleted": job_id}

@app.put("/api/scheduler/job/{job_id}")
async def update_scheduler_job(job_id: str, req: CreateJobRequest):
    try:
        j_type = JobType(req.job_type)
    except ValueError:
        j_type = None
    try:
        job_info = cron_manager.update_job(
            job_id=job_id,
            name=req.name or None,
            schedule_type=req.schedule_type or None,
            schedule_value=req.schedule_value or None,
            job_type=j_type,
            target=req.target or None,
            channel=req.channel or None,
            agent_id=req.agent_id or None,
            parameters=req.parameters,
        )
        return {"status": "ok", "job": job_info}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/scheduler/trigger/{job_id}")
async def trigger_scheduler_job(job_id: str):
    success = await cron_manager.trigger_job(job_id)
    return {"status": "ok", "triggered": success}

@app.post("/api/workspace/file")
async def write_workspace_file(req: WorkspaceFileWriteRequest):
    try:
        msg = workspace.write_file(req.path, req.content)
        return {"status": "ok", "path": req.path, "size": len(req.content), "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/workspace/folder")
async def create_workspace_folder(req: WorkspaceFolderCreateRequest):
    try:
        msg = workspace.create_directory(req.path)
        return {"status": "ok", "message": msg, "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/workspace/zip")
async def create_workspace_zip(req: WorkspaceZipRequest):
    try:
        res = workspace.create_zip(sources=req.sources, zip_name=req.zip_name)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/workspace/download")
async def download_workspace_file(path: str):
    try:
        target = workspace._resolve_safe_path(path)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/workspace/file")
async def delete_workspace_file(path: str):
    try:
        target = workspace._resolve_safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        msg = workspace.delete_file(path)
        return {"status": "ok", "deleted": path, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/companion/exec")
async def proxy_companion_exec(req: CompanionExecRequest):
    url = f"http://{settings.COMPANION_HOST}:{settings.COMPANION_PORT}/exec"
    try:
        async with httpx.AsyncClient(timeout=float(req.timeout_seconds + 5)) as client:
            res = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.COMPANION_AUTH_TOKEN}"},
                json={"command": req.command, "timeout_seconds": req.timeout_seconds}
            )
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Companion proxy error: {e}")

@app.get("/api/companion/screenshot")
async def proxy_companion_screenshot():
    url = f"http://{settings.COMPANION_HOST}:{settings.COMPANION_PORT}/screenshot"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.COMPANION_AUTH_TOKEN}"}
            )
            return Response(content=res.content, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Companion screenshot error: {e}")

@app.post("/api/channels/whatsapp/webhook")
async def whatsapp_webhook(req: Request):
    payload = await req.json()
    sender = payload.get("sender") or payload.get("from") or payload.get("sender_phone")
    text = payload.get("text") or payload.get("message") or payload.get("body")
    if sender and text:
        reply = await whatsapp_manager.handle_incoming_message(
            sender_phone=str(sender),
            text=str(text),
            is_from_me=bool(payload.get("is_from_me", False)),
            push_name=str(payload.get("push_name", "User"))
        )
        return {"status": "ok", "reply": reply}
    return {"status": "ignored", "reply": None}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # Security rate limit check
    allowed, reason = rate_limiter.check_allowed(estimated_tokens=300)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {reason}")

    session_id = req.session_id or "default"
    if session_id not in active_sessions:
        active_sessions[session_id] = SessionContext(session_id=session_id)
    
    ctx = active_sessions[session_id]
    
    target_profile = None
    if req.agent_id:
        target_profile = profile_store.get_profile(req.agent_id)

    try:
        reply = await agent_engine.run(user_prompt=req.message, context=ctx, profile=target_profile)
        rate_limiter.record_request(tokens=500)
        return ChatResponse(
            response=reply,
            session_id=session_id,
            token_stats=tracker.get_summary()
        )
    except Exception as e:
        logger.error(f"Chat execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MULTI-AGENT PROFILES & SOUL.MD API
# ==========================================

@app.get("/api/agents/profiles")
async def get_agent_profiles():
    return [p.model_dump() for p in profile_store.list_profiles()]

@app.post("/api/agents/profiles")
async def create_agent_profile(profile_data: Dict[str, Any]):
    try:
        profile = AgentProfile(**profile_data)
        saved = profile_store.save_profile(profile)
        if saved.id == "lxion_core" and saved.channel_bindings.get("telegram_token"):
            tg_tok = saved.channel_bindings.get("telegram_token")
            settings.TELEGRAM_BOT_TOKEN = tg_tok
            update_env_file({"TELEGRAM_BOT_TOKEN": tg_tok})
            asyncio.create_task(telegram_gateway.start(tg_tok))
        return {"success": True, "profile": saved.model_dump()}
    except Exception as e:
        logger.error(f"Error creating agent profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/agents/profiles/{agent_id}")
async def update_agent_profile(agent_id: str, profile_data: Dict[str, Any]):
    existing = profile_store.get_profile(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    try:
        profile_data["id"] = agent_id
        profile = AgentProfile(**profile_data)
        saved = profile_store.save_profile(profile)
        if saved.id == "lxion_core" and saved.channel_bindings.get("telegram_token"):
            tg_tok = saved.channel_bindings.get("telegram_token")
            settings.TELEGRAM_BOT_TOKEN = tg_tok
            update_env_file({"TELEGRAM_BOT_TOKEN": tg_tok})
            asyncio.create_task(telegram_gateway.start(tg_tok))
        return {"success": True, "profile": saved.model_dump()}
    except Exception as e:
        logger.error(f"Error updating agent profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/agents/profiles/{agent_id}")
async def delete_agent_profile(agent_id: str):
    try:
        success = profile_store.delete_profile(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent profile '{agent_id}' not found")
        return {"success": True, "message": f"Agent '{agent_id}' deleted successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/soul/{agent_id}")
async def get_agent_soul(agent_id: str):
    profile = profile_store.get_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    if agent_id == "lxion_core":
        soul_file = settings.BASE_DIR / "SOUL.md"
        if soul_file.exists():
            return {"agent_id": agent_id, "soul": soul_file.read_text(encoding="utf-8")}
    return {"agent_id": agent_id, "soul": profile.soul_prompt}

@app.put("/api/agents/soul/{agent_id}")
async def update_agent_soul(agent_id: str, data: Dict[str, str]):
    profile = profile_store.get_profile(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    new_soul = data.get("soul", "")
    profile.soul_prompt = new_soul
    profile_store.save_profile(profile)
    if agent_id == "lxion_core":
        soul_file = settings.BASE_DIR / "SOUL.md"
        soul_file.write_text(new_soul, encoding="utf-8")
    return {"success": True, "message": "SOUL updated successfully"}

@app.get("/api/agents/available-tools")
async def get_available_tools():
    all_tools = registry.get_all_tools()
    tools_list = []
    for t in all_tools:
        tools_list.append({
            "name": t.name,
            "description": t.description
        })
    return tools_list

@app.get("/api/agents/available-skills")
async def get_available_skills():
    return skill_manager.list_installed_skills()

@app.get("/api/agents/available-combos")
async def get_available_combos():
    combos = []
    try:
        models = await multi_provider_router.list_models()
        combos = [m.get("id") for m in models if m.get("id")]
    except Exception as e:
        logger.warning(f"Could not load combos from 9Router: {e}")
    if not combos:
        combos = ["wkwk", "gc/gemini-2.5-flash", "ag/claude-sonnet-4-6", "ag/gemini-3.8-flash", "gpt-4o-mini"]
    return {"combos": combos}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("lxion.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)