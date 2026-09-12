from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.scheduler.cron_manager import cron_manager, JobType

class ScheduleJobTool(BaseTool):
    name = "schedule_cron_job"
    description = (
        "Create a scheduled task. Supports dual-mode execution: "
        "'direct_tool' (runs a registered tool directly with NO LLM tokens used, e.g. send_channel_message) or "
        "'ai_prompt' (prompts an AI agent ReAct loop periodically). "
        "Supports flexible schedule types: 'daily' (e.g. '07:00'), 'weekly' (e.g. 'senin,selasa@07:00' or 'mon,wed@07:00'), "
        "'interval' (e.g. '5h', '30m'), 'date' (e.g. '2026-09-15 07:00:00'), or 'cron' ('0 7 * * 1-5'). "
        "Can automatically route outputs to chat channels ('telegram', 'whatsapp', 'discord', or 'none') "
        "and select which agent profile executes the task ('lxion_core', 'sosmed_specialist', etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Descriptive name for the scheduled task (e.g. 'Jadwal Kuliah Senin Pagi' or 'Content Ideation')."
            },
            "schedule_type": {
                "type": "string",
                "enum": ["daily", "weekly", "interval", "date", "cron"],
                "description": "Schedule type: 'daily' (HH:MM), 'weekly' (days@HH:MM), 'interval' (e.g. 5h, 30m), 'date' (YYYY-MM-DD HH:MM:SS), or 'cron' (5-part expression)."
            },
            "schedule_value": {
                "type": "string",
                "description": "Value matching schedule_type: e.g. '07:00' (daily), 'senin,selasa@07:00' (weekly), '5h' (interval), '0 7 * * 1-5' (cron)."
            },
            "job_type": {
                "type": "string",
                "enum": ["direct_tool", "ai_prompt"],
                "description": "Choose 'direct_tool' (0 tokens, deterministic e.g. send_channel_message) or 'ai_prompt' (calls AI agent)."
            },
            "target": {
                "type": "string",
                "description": "If direct_tool: registered tool name (e.g. 'send_channel_message', 'fetch_url'). If ai_prompt: prompt text for the agent."
            },
            "channel": {
                "type": "string",
                "enum": ["none", "telegram", "whatsapp", "discord"],
                "description": "Chat channel where notifications or AI responses should be routed to. Default is 'none'."
            },
            "agent_id": {
                "type": "string",
                "description": "Target agent profile to execute the prompt (e.g. 'lxion_core', 'sosmed_specialist'). Default is 'lxion_core'."
            },
            "parameters": {
                "type": "object",
                "description": "Parameters for the direct tool (e.g. {'channel': 'telegram', 'message': 'Kuliah jam 7'} for send_channel_message)."
            }
        },
        "required": ["name", "schedule_type", "schedule_value", "job_type", "target"]
    }

    async def execute(
        self,
        name: str,
        schedule_type: str,
        schedule_value: str,
        job_type: str,
        target: str,
        channel: Optional[str] = "none",
        agent_id: Optional[str] = "lxion_core",
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            jt = JobType(job_type)
            job = cron_manager.add_job(
                name=name,
                schedule_type=schedule_type,
                schedule_value=schedule_value,
                job_type=jt,
                target=target,
                channel=channel or "none",
                agent_id=agent_id or "lxion_core",
                parameters=parameters or {}
            )
            return {"success": True, "job": job}
        except Exception as e:
            return {"success": False, "error": str(e)}

class SendChannelMessageTool(BaseTool):
    name = "send_channel_message"
    description = (
        "Directly send a message or notification to an external chat channel "
        "(Telegram, WhatsApp, Discord) without consuming LLM tokens. Ideal for deterministic scheduled alerts, reminders, or notifications."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": ["telegram", "whatsapp", "discord"],
                "description": "Destination channel to send the message to."
            },
            "message": {
                "type": "string",
                "description": "The message text to send."
            },
            "recipient_id": {
                "type": "string",
                "description": "Optional recipient ID (phone number for WhatsApp, chat ID for Telegram, channel ID for Discord). Defaults to 'default'."
            }
        },
        "required": ["channel", "message"]
    }

    async def execute(
        self,
        channel: str,
        message: str,
        recipient_id: Optional[str] = "default",
        **kwargs
    ) -> Dict[str, Any]:
        from lxion.channels.bus import message_bus, ChannelType, OutboundMessage
        try:
            ch_enum = ChannelType(channel.lower())
            await message_bus.send_outbound(
                OutboundMessage(
                    channel=ch_enum,
                    recipient_id=recipient_id or "default",
                    text=message
                )
            )
            return {
                "success": True,
                "channel": channel,
                "recipient": recipient_id,
                "message_sent": message
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class ListJobsTool(BaseTool):
    name = "list_cron_jobs"
    description = "List all active scheduled cron, daily, weekly, and interval tasks."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        return cron_manager.list_jobs()

class CancelJobTool(BaseTool):
    name = "cancel_cron_job"
    description = "Cancel and delete a scheduled cron task by its Job ID."
    parameters = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to cancel."
            }
        },
        "required": ["job_id"]
    }

    async def execute(self, job_id: str, **kwargs) -> Dict[str, Any]:
        ok = cron_manager.remove_job(job_id)
        return {"success": ok, "job_id": job_id}

class GetJobHistoryTool(BaseTool):
    name = "get_cron_history"
    description = "Retrieve execution logs and results of recently fired cron jobs."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of recent history records to return (default 10)."
            }
        }
    }

    async def execute(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return cron_manager.get_history(limit=limit)

class CronSchedulerTool(BaseTool):
    name = "cron_scheduler"
    description = (
        "Unified task scheduler & cron manager. Supported actions: "
        "'schedule' (create recurring/daily/weekly/interval/date task), "
        "'list' (view all active jobs), 'cancel' (delete scheduled job), "
        "'history' (view execution logs and timing telemetry)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["schedule", "list", "cancel", "history"],
                "description": "Scheduler operation to perform."
            },
            "name": {
                "type": "string",
                "description": "Human-readable label for the job (for 'schedule')."
            },
            "schedule_type": {
                "type": "string",
                "enum": ["interval", "daily", "weekly", "date", "cron"],
                "description": "Trigger cadence (for 'schedule')."
            },
            "schedule_value": {
                "type": "string",
                "description": "Cadence value, e.g. '5m', '07:00', 'senin,rabu@07:00', '2026-09-15 07:00:00'."
            },
            "job_type": {
                "type": "string",
                "enum": ["direct_tool", "ai_prompt"],
                "description": "'direct_tool' (0 tokens, deterministic) or 'ai_prompt' (calls AI agent)."
            },
            "target": {
                "type": "string",
                "description": "Tool name (if direct_tool) or prompt instructions (if ai_prompt)."
            },
            "channel": {
                "type": "string",
                "enum": ["telegram", "whatsapp", "discord", "none"],
                "description": "Destination channel to forward output to."
            },
            "agent_id": {
                "type": "string",
                "description": "Agent profile ID to execute the task (default 'lxion_core')."
            },
            "parameters": {
                "type": "object",
                "description": "Parameters for the direct tool."
            },
            "job_id": {
                "type": "string",
                "description": "The ID of the job to cancel (for 'cancel')."
            },
            "limit": {
                "type": "integer",
                "description": "Number of recent history records to return (for 'history', default 10)."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        name: Optional[str] = None,
        schedule_type: Optional[str] = None,
        schedule_value: Optional[str] = None,
        job_type: str = "ai_prompt",
        target: Optional[str] = None,
        channel: str = "none",
        agent_id: str = "lxion_core",
        parameters: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> Any:
        act = action.strip().lower()
        if act == "list":
            return cron_manager.list_jobs()
        elif act == "history":
            return cron_manager.get_history(limit=limit)
        elif act == "cancel":
            if not job_id:
                return {"success": False, "error": "Parameter 'job_id' is required for 'cancel' action."}
            ok = cron_manager.remove_job(job_id)
            return {"success": ok, "job_id": job_id}
        elif act == "schedule":
            if not name or not schedule_type or not schedule_value or not target:
                return {
                    "success": False,
                    "error": "Parameters 'name', 'schedule_type', 'schedule_value', and 'target' are required for 'schedule'."
                }
            try:
                jt = JobType(job_type.lower()) if job_type.lower() in [e.value for e in JobType] else JobType.AI_PROMPT
                job = cron_manager.add_job(
                    name=name,
                    schedule_type=schedule_type,
                    schedule_value=schedule_value,
                    job_type=jt,
                    target=target,
                    channel=channel or "none",
                    agent_id=agent_id or "lxion_core",
                    parameters=parameters or {}
                )
                return {"success": True, "job": job}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": f"Unknown scheduler action: '{action}'. Choose: 'schedule', 'list', 'cancel', 'history'."}
