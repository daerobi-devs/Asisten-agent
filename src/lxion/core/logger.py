import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from rich.console import Console
from rich.logging import RichHandler
from lxion.core.config import settings

# Safe console for Windows cp1252 / UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(force_terminal=True, legacy_windows=False)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            markup=False  # Avoid markup errors on raw logs
        )
    ]
)

logger = logging.getLogger("lxion")

class AuditLogger:
    @staticmethod
    def log_event(event_type: str, actor: str, details: Dict[str, Any]):
        timestamp = datetime.now(timezone.utc).isoformat()
        audit_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "actor": actor,
            "details": details
        }
        logger.info(f"[AUDIT] {event_type} by {actor}: {json.dumps(details, default=str)}")
        
        try:
            settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_file = settings.LOGS_DIR / "audit.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist audit log to file: {e}")