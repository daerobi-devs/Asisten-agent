from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Agent Metadata
    AGENT_NAME: str = "LXION"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # 9Router Primary LLM Gateway
    NINE_ROUTER_BASE_URL: str = Field(default="https://9router.daeroom.my.id/v1")
    NINE_ROUTER_API_KEY: str = Field(default="")
    DEFAULT_MODEL: str = Field(default="auto")

    # Direct Providers (Optional fallbacks)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_BASE_URL: str = Field(default="https://api.anthropic.com/v1")
    GEMINI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None

    # Security & Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_TOKENS_PER_MINUTE: int = Field(default=100_000)

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://lxion:lxion_secret_2026@localhost:5432/lxion_db"
    )
    POSTGRES_USER: str = "lxion"
    POSTGRES_PASSWORD: str = "lxion_secret_2026"
    POSTGRES_DB: str = "lxion_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    WORKSPACE_DIR: Path = Field(default=Path("./workspace"))
    SKILLS_DIR: Path = Field(default=Path("./.agents/skills"))
    LOGS_DIR: Path = Field(default=Path("./logs"))

    # Server API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Channels
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ALLOWED_USERS: list[str] = Field(default_factory=list)
    DISCORD_BOT_TOKEN: Optional[str] = None
    WHATSAPP_SESSION_PATH: str = "./whatsapp_sessions"

    # Companion Laptop (Tailscale)
    COMPANION_HOST: Optional[str] = None
    COMPANION_PORT: int = 9099
    COMPANION_AUTH_TOKEN: Optional[str] = None

    # Timezone (used by APScheduler & all scheduled jobs)
    TIMEZONE: str = "Asia/Jakarta"

    # WhatsApp Baileys sidecar URL
    WHATSAPP_SIDECAR_URL: str = "http://whatsapp-sidecar:3001"

settings = Settings()

def update_env_file(updates: dict) -> bool:
    """Safely update or append key-value pairs in the .env file."""
    env_path = Path(".env")
    lines = []
    existing_keys = set()
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                existing_keys.add(k)
                continue
        new_lines.append(line)
        
    for k, v in updates.items():
        if k not in existing_keys:
            new_lines.append(f"{k}={v}")
            
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True