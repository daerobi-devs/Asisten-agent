from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.agents.profile_store import profile_store, AgentProfile
from lxion.core.logger import logger

class CreateAgentProfileTool(BaseTool):
    name = "create_agent_profile"
    description = "Create a new specialized sub-agent profile with custom persona (SOUL), specific tools subset, provider, and model combo."
    parameters = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "Unique identifier slug (e.g. 'sosmed_specialist', 'code_reviewer', 'market_analyst')."
            },
            "name": {
                "type": "string",
                "description": "Display name of the agent."
            },
            "description": {
                "type": "string",
                "description": "Short explanation of the agent's purpose and role."
            },
            "soul_prompt": {
                "type": "string",
                "description": "The persona, tone, guidelines, and behavioral instructions for this agent."
            },
            "provider": {
                "type": "string",
                "description": "LLM provider: '9router' (default), 'openai', 'anthropic', 'custom'."
            },
            "model": {
                "type": "string",
                "description": "Model or 9Router combo identifier (e.g. 'wkwk', 'gc/gemini-2.5-flash', 'gpt-4o-mini')."
            },
            "assigned_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific tools permitted for this agent (e.g. ['read_file', 'write_file', 'fetch_url']). Pass ['*'] for all."
            },
            "assigned_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of skill names attached to this agent (e.g. ['taste-skill'])."
            },
            "discord_token": {
                "type": "string",
                "description": "Optional dedicated Discord bot token for this sub-agent."
            },
            "telegram_token": {
                "type": "string",
                "description": "Optional dedicated Telegram bot token for this sub-agent."
            }
        },
        "required": ["id", "name", "description"]
    }

    async def execute(
        self,
        id: str,
        name: str,
        description: str,
        soul_prompt: str = "",
        provider: str = "9router",
        model: str = "wkwk",
        assigned_tools: Optional[List[str]] = None,
        assigned_skills: Optional[List[str]] = None,
        discord_token: Optional[str] = None,
        telegram_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            channel_bindings = {}
            if discord_token:
                channel_bindings["discord_token"] = discord_token
            if telegram_token:
                channel_bindings["telegram_token"] = telegram_token

            tools = assigned_tools if assigned_tools is not None else ["read_file", "write_file", "fetch_url"]
            skills = assigned_skills or []

            profile = AgentProfile(
                id=id,
                name=name,
                description=description,
                soul_prompt=soul_prompt or f"You are {name}, a specialized assistant.",
                provider=provider or "9router",
                model=model or "wkwk",
                assigned_tools=tools,
                assigned_skills=skills,
                channel_bindings=channel_bindings,
                is_primary=False
            )
            saved = profile_store.save_profile(profile)
            return {
                "success": True,
                "message": f"Successfully created agent '{saved.name}' (ID: {saved.id})",
                "profile": saved.model_dump()
            }
        except Exception as e:
            logger.error(f"Failed to create agent profile: {e}")
            return {"success": False, "error": str(e)}

class UpdateAgentProfileTool(BaseTool):
    name = "update_agent_profile"
    description = "Update an existing agent profile's persona, assigned tools, skills, provider, or model."
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Agent identifier to update."},
            "name": {"type": "string", "description": "New display name."},
            "description": {"type": "string", "description": "New description."},
            "soul_prompt": {"type": "string", "description": "Updated SOUL/persona prompt."},
            "provider": {"type": "string", "description": "Updated LLM provider."},
            "model": {"type": "string", "description": "Updated model/combo."},
            "assigned_tools": {"type": "array", "items": {"type": "string"}},
            "assigned_skills": {"type": "array", "items": {"type": "string"}},
            "discord_token": {"type": "string"},
            "telegram_token": {"type": "string"}
        },
        "required": ["id"]
    }

    async def execute(self, id: str, **kwargs) -> Dict[str, Any]:
        profile = profile_store.get_profile(id)
        if not profile:
            return {"success": False, "error": f"Agent profile '{id}' not found."}

        for field in ["name", "description", "soul_prompt", "provider", "model"]:
            if field in kwargs and kwargs[field] is not None:
                setattr(profile, field, kwargs[field])

        if "assigned_tools" in kwargs and kwargs["assigned_tools"] is not None:
            profile.assigned_tools = kwargs["assigned_tools"]

        if "assigned_skills" in kwargs and kwargs["assigned_skills"] is not None:
            profile.assigned_skills = kwargs["assigned_skills"]

        if "discord_token" in kwargs:
            profile.channel_bindings["discord_token"] = kwargs["discord_token"]
        if "telegram_token" in kwargs:
            profile.channel_bindings["telegram_token"] = kwargs["telegram_token"]

        saved = profile_store.save_profile(profile)
        return {
            "success": True,
            "message": f"Agent '{saved.id}' updated.",
            "profile": saved.model_dump()
        }

class ListAgentProfilesTool(BaseTool):
    name = "list_agent_profiles"
    description = "List all available agent profiles, their roles, models, and assigned tools."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        profiles = profile_store.list_profiles()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "provider": p.provider,
                "model": p.model,
                "tools_count": len(p.assigned_tools),
                "skills": p.assigned_skills,
                "is_primary": p.is_primary,
                "channels": list(p.channel_bindings.keys())
            }
            for p in profiles
        ]

class DeleteAgentProfileTool(BaseTool):
    name = "delete_agent_profile"
    description = "Delete a sub-agent profile. Primary agent (LXION) cannot be deleted."
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Agent profile ID to delete."}
        },
        "required": ["id"]
    }

    async def execute(self, id: str, **kwargs) -> Dict[str, Any]:
        try:
            success = profile_store.delete_profile(id)
            if success:
                return {"success": True, "message": f"Agent profile '{id}' deleted."}
            return {"success": False, "error": f"Agent profile '{id}' not found."}
        except Exception as e:
            return {"success": False, "error": str(e)}

class AgentProfilesTool(BaseTool):
    name = "agent_profiles"
    description = (
        "Unified agent factory for managing specialized sub-agent personas (SOUL), models, and tools. "
        "Supported actions: 'list' (view all profiles), 'create' (define new agent), "
        "'update' (modify settings), 'delete' (remove sub-agent)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "update", "delete"],
                "description": "Agent management operation to perform."
            },
            "id": {
                "type": "string",
                "description": "Unique agent identifier slug (e.g. 'sosmed_specialist', 'coder')."
            },
            "name": {
                "type": "string",
                "description": "Display name of the agent."
            },
            "description": {
                "type": "string",
                "description": "Short explanation of the agent's purpose and role."
            },
            "soul_prompt": {
                "type": "string",
                "description": "The persona, tone, guidelines, and behavioral instructions for this agent."
            },
            "provider": {
                "type": "string",
                "description": "LLM provider: '9router', 'openai', 'anthropic', 'custom'."
            },
            "model": {
                "type": "string",
                "description": "Model or 9Router combo identifier (e.g. 'wkwk', 'gc/gemini-2.5-flash')."
            },
            "assigned_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of permitted tools or ['*'] for all."
            },
            "assigned_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of skill names attached to this agent."
            },
            "discord_token": {
                "type": "string",
                "description": "Optional Discord bot token for this sub-agent."
            },
            "telegram_token": {
                "type": "string",
                "description": "Optional Telegram bot token for this sub-agent."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        soul_prompt: str = "",
        provider: str = "9router",
        model: Optional[str] = None,
        assigned_tools: Optional[List[str]] = None,
        assigned_skills: Optional[List[str]] = None,
        discord_token: Optional[str] = None,
        telegram_token: Optional[str] = None,
        **kwargs
    ) -> Any:
        act = action.strip().lower()
        if act == "list":
            profiles = profile_store.list_profiles()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "provider": p.provider,
                    "model": p.model,
                    "tools_count": len(p.assigned_tools),
                    "skills": p.assigned_skills,
                    "is_primary": p.is_primary,
                    "channels": list(p.channel_bindings.keys())
                }
                for p in profiles
            ]

        elif act == "create":
            if not id or not name:
                return {"success": False, "error": "Parameters 'id' and 'name' are required for 'create' action."}
            from lxion.core.config import settings
            chosen_model = model or getattr(settings, "DEFAULT_MODEL", "wkwk") or "wkwk"
            bindings = {}
            if discord_token:
                bindings["discord_token"] = discord_token
            if telegram_token:
                bindings["telegram_token"] = telegram_token

            profile = AgentProfile(
                id=id,
                name=name,
                description=description or "",
                soul_prompt=soul_prompt,
                provider=provider,
                model=chosen_model,
                assigned_tools=assigned_tools if assigned_tools is not None else ["*"],
                assigned_skills=assigned_skills or [],
                channel_bindings=bindings
            )
            saved = profile_store.save_profile(profile)
            return {"success": True, "profile": saved.model_dump()}

        elif act == "update":
            if not id:
                return {"success": False, "error": "Parameter 'id' is required for 'update' action."}
            existing = profile_store.get_profile(id)
            if not existing:
                return {"success": False, "error": f"Agent profile '{id}' not found."}
            if name is not None:
                existing.name = name
            if description is not None:
                existing.description = description
            if soul_prompt:
                existing.soul_prompt = soul_prompt
            if provider:
                existing.provider = provider
            if model:
                existing.model = model
            if assigned_tools is not None:
                existing.assigned_tools = assigned_tools
            if assigned_skills is not None:
                existing.assigned_skills = assigned_skills
            if discord_token:
                existing.channel_bindings["discord_token"] = discord_token
            if telegram_token:
                existing.channel_bindings["telegram_token"] = telegram_token

            saved = profile_store.save_profile(existing)
            return {"success": True, "profile": saved.model_dump()}

        elif act == "delete":
            if not id:
                return {"success": False, "error": "Parameter 'id' is required for 'delete' action."}
            try:
                success = profile_store.delete_profile(id)
                if success:
                    return {"success": True, "message": f"Agent profile '{id}' deleted."}
                return {"success": False, "error": f"Agent profile '{id}' not found."}
            except Exception as e:
                return {"success": False, "error": str(e)}

        else:
            return {"success": False, "error": f"Unknown agent action: '{action}'. Choose: 'list', 'create', 'update', 'delete'."}
