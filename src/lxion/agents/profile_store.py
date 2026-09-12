import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class AgentProfile(BaseModel):
    id: str = Field(..., description="Unique slug identifier for the agent (e.g. lxion_core, sosmed_agent)")
    name: str = Field(..., description="Display name for the agent")
    avatar: str = Field(default="cpu", description="Lucide icon name (e.g. cpu, bot, share-2, code, search)")
    description: str = Field(default="", description="Brief description of the agent's role and purpose")
    soul_prompt: str = Field(default="", description="Custom persona, tone, instructions, or SOUL.md prompt")
    provider: str = Field(default="9router", description="LLM provider: '9router', 'openai', 'anthropic', 'custom'")
    model: str = Field(default="wkwk", description="Model name or 9Router combo identifier (e.g. wkwk, gc/gemini-2.5-flash)")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    assigned_tools: List[str] = Field(default_factory=lambda: ["*"], description="List of tool names permitted, or ['*'] for all")
    assigned_skills: List[str] = Field(default_factory=list, description="List of active skill names (e.g. ['taste-skill'])")
    channel_bindings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dedicated channel tokens (e.g. {'discord_token': '...', 'telegram_token': '...'}). WhatsApp is strictly reserved for primary."
    )
    is_primary: bool = Field(default=False, description="Whether this is the root Primary Agent (LXION Core)")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class AgentProfileStore:
    def __init__(self, store_file: Optional[Path] = None):
        if store_file:
            self.store_file = Path(store_file)
        else:
            self.store_file = (settings.WORKSPACE_DIR / "agents" / "profiles.json").resolve()
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, AgentProfile] = {}
        self.load_all()
        self.ensure_defaults()

    def _read_soul_md(self) -> str:
        soul_path = settings.BASE_DIR / "SOUL.md"
        if soul_path.exists():
            try:
                return soul_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not read SOUL.md: {e}")
        return ""

    def ensure_defaults(self):
        """Seed primary LXION Core and an example specialist agent if not present."""
        modified = False
        if "lxion_core" not in self._profiles:
            soul_content = self._read_soul_md()
            primary = AgentProfile(
                id="lxion_core",
                name="LXION Core",
                avatar="cpu",
                description="Primary Autonomous Engineering Intelligence & Personal Assistant. Exclusive operator of the WhatsApp Gateway.",
                soul_prompt=soul_content or "You are LXION, the primary autonomous intelligence for ADVAN.",
                provider="9router",
                model="wkwk",
                temperature=0.7,
                assigned_tools=["*"],
                assigned_skills=["taste-skill"],
                channel_bindings={"whatsapp": True},
                is_primary=True
            )
            self._profiles["lxion_core"] = primary
            modified = True

        if "sosmed_specialist" not in self._profiles:
            sosmed = AgentProfile(
                id="sosmed_specialist",
                name="Sosmed & Content Specialist",
                avatar="share-2",
                description="Spesialis riset tren media sosial, pembuatan copy konten viral, dan penjadwalan publikasi.",
                soul_prompt="Anda adalah Sosmed Specialist. Tugas Anda adalah meriset tren, menulis copy memikat, dan menyusun rencana konten media sosial yang berdampak tinggi. Berikan copywriting yang menarik, ringkas, dan persuasif.",
                provider="9router",
                model="wkwk",
                temperature=0.7,
                assigned_tools=["fetch_url", "write_file", "read_file", "kanban_create_task", "kanban_get_board"],
                assigned_skills=[],
                channel_bindings={},
                is_primary=False
            )
            self._profiles["sosmed_specialist"] = sosmed
            modified = True

        if modified:
            self._persist()

    def load_all(self) -> Dict[str, AgentProfile]:
        if not self.store_file.exists():
            return {}
        try:
            data = json.loads(self.store_file.read_text(encoding="utf-8"))
            self._profiles = {item["id"]: AgentProfile(**item) for item in data}
            logger.info(f"Loaded {len(self._profiles)} agent profiles from {self.store_file}")
        except Exception as e:
            logger.error(f"Failed to load agent profiles from {self.store_file}: {e}")
            self._profiles = {}
        return self._profiles

    def _persist(self):
        try:
            data = [p.model_dump() for p in self._profiles.values()]
            self.store_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save agent profiles to {self.store_file}: {e}")

    def list_profiles(self) -> List[AgentProfile]:
        return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> Optional[AgentProfile]:
        return self._profiles.get(profile_id)

    def save_profile(self, profile: AgentProfile) -> AgentProfile:
        """Create or update an agent profile with security guardrails."""
        # Clean slug
        profile.id = profile.id.strip().lower().replace(" ", "_")

        # Guardrails: WhatsApp channel exclusivity
        if not profile.is_primary and "whatsapp" in profile.channel_bindings:
            logger.warning(f"Rejecting WhatsApp binding for non-primary agent '{profile.id}'")
            profile.channel_bindings.pop("whatsapp", None)

        if profile.id == "lxion_core":
            profile.is_primary = True
        else:
            # Sub-agents cannot claim primary role
            profile.is_primary = False

        profile.updated_at = time.time()
        self._profiles[profile.id] = profile
        self._persist()

        AuditLogger.log_event("AGENT_PROFILE_SAVED", "agent_store", {
            "profile_id": profile.id,
            "name": profile.name,
            "provider": profile.provider,
            "model": profile.model,
            "is_primary": profile.is_primary
        })
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        """Delete an agent profile. Primary profile cannot be deleted."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        if profile.is_primary or profile.id == "lxion_core":
            raise ValueError("Primary Agent (LXION Core) is protected and cannot be deleted.")

        del self._profiles[profile_id]
        self._persist()

        AuditLogger.log_event("AGENT_PROFILE_DELETED", "agent_store", {
            "profile_id": profile_id
        })
        return True

profile_store = AgentProfileStore()
