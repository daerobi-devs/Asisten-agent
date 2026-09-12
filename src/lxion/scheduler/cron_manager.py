import asyncio
import json
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class JobType(str, Enum):
    DIRECT_TOOL = "direct_tool"  # Executes a tool directly WITHOUT invoking AI (0 token cost, deterministic)
    AI_PROMPT = "ai_prompt"      # Triggers the Agent ReAct loop with a dynamic prompt

INDONESIAN_DAYS = {
    "senin": "mon",
    "selasa": "tue",
    "rabu": "wed",
    "kamis": "thu",
    "jumat": "fri",
    "jum'at": "fri",
    "sabtu": "sat",
    "minggu": "sun"
}

def parse_schedule_trigger(schedule_type: str, schedule_value: str):
    """Parse flexible schedule strings into APScheduler triggers."""
    st = schedule_type.strip().lower()
    val = schedule_value.strip()

    if st == "interval":
        val_lower = val.lower()
        if val_lower.endswith("s"):
            return IntervalTrigger(seconds=int(val_lower[:-1]))
        elif val_lower.endswith("m"):
            return IntervalTrigger(minutes=int(val_lower[:-1]))
        elif val_lower.endswith("h"):
            return IntervalTrigger(hours=int(val_lower[:-1]))
        elif val_lower.endswith("d"):
            return IntervalTrigger(days=int(val_lower[:-1]))
        else:
            return IntervalTrigger(seconds=int(val_lower))

    elif st == "daily":
        # e.g. "07:00" or "7:00"
        parts = val.split(":")
        if len(parts) >= 2:
            return CronTrigger(hour=int(parts[0]), minute=int(parts[1]))
        else:
            raise ValueError(f"Invalid daily time format '{val}'. Expected 'HH:MM' (e.g. 07:00)")

    elif st == "weekly":
        # e.g. "mon,wed,fri@07:00" or "senin,selasa,rabu@07:00"
        if "@" in val:
            days_part, time_part = val.split("@", 1)
        else:
            days_part, time_part = val, "07:00"

        time_parts = time_part.strip().split(":")
        hour = int(time_parts[0]) if len(time_parts) >= 1 else 7
        minute = int(time_parts[1]) if len(time_parts) >= 2 else 0

        # Translate Indonesian day names if present
        clean_days = []
        for d in days_part.replace(" ", "").split(","):
            d_lower = d.lower()
            clean_days.append(INDONESIAN_DAYS.get(d_lower, d_lower))
        dow_str = ",".join(clean_days)
        return CronTrigger(day_of_week=dow_str, hour=hour, minute=minute)

    elif st == "date":
        # Specific date time, e.g. "2026-09-15 07:00:00" or "2026-09-15T07:00"
        clean_val = val.replace("T", " ")
        if len(clean_val.split(":")) == 2:
            clean_val += ":00"
        return DateTrigger(run_date=clean_val)

    elif st == "cron":
        parts = val.split()
        if len(parts) == 5:
            return CronTrigger.from_crontab(val)
        else:
            raise ValueError(f"Invalid 5-part cron syntax: '{val}'")

    else:
        raise ValueError(
            f"Unsupported schedule_type '{schedule_type}'. Use 'interval', 'daily', 'weekly', 'date', or 'cron'."
        )

class CronJobManager:
    def __init__(self, persistence_file: Optional[Path] = None):
        self.scheduler = AsyncIOScheduler()
        self.persistence_file = (persistence_file or settings.WORKSPACE_DIR / "cron_jobs.json").resolve()
        self.job_history: List[Dict[str, Any]] = []
        self._jobs_meta: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self.agent_runner: Optional[Callable] = None

    def set_agent_runner(self, runner: Callable):
        self.agent_runner = runner

    def start(self):
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("[OK] APScheduler cron engine started.")
            self._load_saved_jobs()

    def stop(self):
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[OK] APScheduler cron engine stopped.")

    def _load_saved_jobs(self):
        if self.persistence_file.exists():
            try:
                data = json.loads(self.persistence_file.read_text(encoding="utf-8"))
                for item in data:
                    try:
                        self.add_job(
                            job_id=item["id"],
                            name=item["name"],
                            schedule_type=item["schedule_type"],
                            schedule_value=item["schedule_value"],
                            job_type=JobType(item["job_type"]),
                            target=item["target"],
                            channel=item.get("channel", "none"),
                            agent_id=item.get("agent_id", "lxion_core"),
                            parameters=item.get("parameters", {}),
                            persist=False
                        )
                    except Exception as e:
                        logger.warning(f"Could not restore cron job {item.get('id')}: {e}")
            except Exception as e:
                logger.error(f"Failed to read cron jobs file: {e}")

    def _save_jobs(self):
        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            self.persistence_file.write_text(json.dumps(list(self._jobs_meta.values()), indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to persist cron jobs: {e}")

    def add_job(
        self,
        name: str,
        schedule_type: str,  # 'interval', 'daily', 'weekly', 'date', or 'cron'
        schedule_value: str, # e.g. '60s', '07:00', 'mon,wed@07:00', '2026-09-15 07:00:00'
        job_type: JobType,
        target: str,         # tool name (for DIRECT_TOOL) or prompt text (for AI_PROMPT)
        channel: Optional[str] = "none",  # 'telegram', 'whatsapp', 'discord', or 'none'
        agent_id: Optional[str] = "lxion_core",
        parameters: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        persist: bool = True
    ) -> Dict[str, Any]:
        jid = job_id or f"job_{int(time.time()*1000)}"
        parameters = parameters or {}
        channel_clean = (channel or "none").lower().strip()
        agent_id_clean = (agent_id or "lxion_core").strip()

        # Build trigger
        trigger = parse_schedule_trigger(schedule_type, schedule_value)

        async def _job_wrapper():
            start_t = time.time()
            res_entry = {
                "job_id": jid,
                "name": name,
                "job_type": job_type.value,
                "channel": channel_clean,
                "agent_id": agent_id_clean,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success",
                "output": None,
                "error": None
            }
            try:
                output_text = None
                if job_type == JobType.DIRECT_TOOL:
                    from lxion.tools.registry import registry
                    tool = registry.get_tool(target)
                    if not tool:
                        raise RuntimeError(f"Direct tool '{target}' not found in registry.")
                    output = await tool.execute(**parameters)
                    output_text = str(output)
                    res_entry["output"] = output_text[:500]
                    AuditLogger.log_event("CRON_DIRECT_EXEC", "scheduler", {
                        "job_id": jid, "tool": target, "params": parameters, "channel": channel_clean
                    })

                    # If channel routing is specified and tool wasn't already send_channel_message
                    if channel_clean != "none" and target != "send_channel_message":
                        from lxion.channels.bus import message_bus, ChannelType, OutboundMessage
                        try:
                            ch_enum = ChannelType(channel_clean)
                            await message_bus.send_outbound(
                                OutboundMessage(channel=ch_enum, recipient_id="default", text=output_text)
                            )
                            logger.info(f"✓ Forwarded tool output to {channel_clean} for cron '{name}'")
                        except Exception as ce:
                            logger.warning(f"Could not forward tool output to {channel_clean}: {ce}")

                elif job_type == JobType.AI_PROMPT:
                    from lxion.agents.profile_store import profile_store
                    from lxion.core.agent import Agent
                    target_profile = profile_store.get_profile(agent_id_clean)
                    agent = Agent(profile=target_profile)
                    output = await agent.run(target)
                    output_text = str(output)
                    res_entry["output"] = output_text[:500]
                    AuditLogger.log_event("CRON_AI_EXEC", "scheduler", {
                        "job_id": jid, "prompt": target, "agent_id": agent_id_clean, "channel": channel_clean
                    })

                    # If channel routing is specified, forward AI response to channel!
                    if channel_clean != "none":
                        from lxion.channels.bus import message_bus, ChannelType, OutboundMessage
                        try:
                            ch_enum = ChannelType(channel_clean)
                            await message_bus.send_outbound(
                                OutboundMessage(channel=ch_enum, recipient_id="default", text=output_text)
                            )
                            logger.info(f"✓ Forwarded AI output to {channel_clean} for cron '{name}'")
                        except Exception as ce:
                            logger.warning(f"Could not forward AI output to {channel_clean}: {ce}")

            except Exception as exc:
                res_entry["status"] = "error"
                res_entry["error"] = str(exc)
                logger.error(f"Cron job {jid} failed: {exc}")
            finally:
                res_entry["duration_ms"] = round((time.time() - start_t) * 1000, 2)
                self.job_history.append(res_entry)
                if len(self.job_history) > 100:
                    self.job_history.pop(0)

        self.scheduler.add_job(
            _job_wrapper,
            trigger=trigger,
            id=jid,
            name=name,
            replace_existing=True
        )

        job_info = {
            "id": jid,
            "name": name,
            "schedule_type": schedule_type,
            "schedule_value": schedule_value,
            "job_type": job_type.value,
            "target": target,
            "channel": channel_clean,
            "agent_id": agent_id_clean,
            "parameters": parameters,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self._jobs_meta[jid] = job_info

        if persist:
            self._save_jobs()

        logger.info(
            f"[OK] Registered cron job '{name}' [{job_type.value}] -> {schedule_type}({schedule_value}) [Target: {channel_clean} | Agent: {agent_id_clean}]"
        )
        return job_info

    def remove_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            self._jobs_meta.pop(job_id, None)
            self._save_jobs()
            logger.info(f"[OK] Removed cron job '{job_id}'")
            return True
        except Exception:
            return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs = []
        for j in self.scheduler.get_jobs():
            meta = self._jobs_meta.get(j.id, {})
            jobs.append({
                "id": j.id,
                "name": meta.get("name") or j.name,
                "schedule_type": meta.get("schedule_type", "interval"),
                "schedule_value": meta.get("schedule_value", ""),
                "job_type": meta.get("job_type", "direct_tool"),
                "target": meta.get("target", ""),
                "channel": meta.get("channel", "none"),
                "agent_id": meta.get("agent_id", "lxion_core"),
                "parameters": meta.get("parameters", {}),
                "created_at": meta.get("created_at"),
                "next_run": str(getattr(j, "next_run_time", None)) if getattr(j, "next_run_time", None) else None
            })
        return jobs

    async def trigger_job(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)
        if job:
            func = job.func
            if asyncio.iscoroutinefunction(func):
                asyncio.create_task(func())
            else:
                func()
            return True
        return False

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.job_history[-limit:]

cron_manager = CronJobManager()
