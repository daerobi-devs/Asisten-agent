import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List, Optional, Any
from lxion.core.config import settings
from lxion.core.logger import logger
from lxion.core.context import Message, Role, SessionContext, ToolCall, FunctionCall
from lxion.llm.router_client import NineRouterClient
from lxion.llm.multi_provider import multi_provider_router, MultiProviderRouter
from lxion.tools.registry import registry
from lxion.agents.profile_store import AgentProfile, profile_store

SYSTEM_PROMPT = """You are LXION, a powerful, persistent, and autonomous AI engineering assistant running on self-hosted infrastructure.
You operate with strict engineering discipline, proactivity, and high accuracy.

Infrastructure Context:
- Primary LLM Gateway: 9Router (self-hosted at https://9router.daeroom.my.id/v1) with smart multi-tier fallbacks.
- Network: Tailscale secure private mesh connecting Proxmox, Coolify, and local Windows companion.
- Storage & Workspace: Persistent Docker volumes, PostgreSQL + pgvector for structured memory, and Git versioning.

Operating Rules:
1. Always use available tools proactively to inspect files, execute tasks, fetch info, or run tests.
2. Maintain clean, robust code with zero fluff.
3. If a task requires multiple steps, break it down logically and execute step-by-step.
4. Always provide truthful, accurate, and concise answers.
"""

def load_skill_prompt(skill_name: str) -> str:
    """Dynamically read instructions from .agents/skills/<name>/SKILL.md if attached."""
    skill_path = settings.BASE_DIR / ".agents" / "skills" / skill_name / "SKILL.md"
    if skill_path.exists():
        try:
            content = skill_path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return content.strip()
        except Exception as e:
            logger.warning(f"Could not load skill '{skill_name}': {e}")
    return ""

class Agent:
    def __init__(
        self,
        router_client: Optional[Any] = None,
        model: Optional[str] = None,
        max_iterations: int = 10,
        profile: Optional[AgentProfile] = None
    ):
        self.client = router_client or multi_provider_router
        self.profile = profile or profile_store.get_profile("lxion_core")
        self.model = model or (self.profile.model if self.profile else settings.DEFAULT_MODEL)
        self.max_iterations = max_iterations
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        base = (self.profile.soul_prompt if self.profile and self.profile.soul_prompt else SYSTEM_PROMPT)
        if self.profile and self.profile.assigned_skills:
            for skill_name in self.profile.assigned_skills:
                skill_doc = load_skill_prompt(skill_name)
                if skill_doc:
                    base += f"\n\n--- DYNAMIC SKILL: {skill_name} ---\n{skill_doc}"
        return base

    async def run(
        self,
        user_prompt: str,
        context: Optional[SessionContext] = None,
        profile: Optional[AgentProfile] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_end: Optional[Callable[[str, Any], None]] = None
    ) -> str:
        """Run the agentic ReAct loop for a single user turn with profile awareness."""
        active_profile = profile or self.profile
        if active_profile:
            self.profile = active_profile
            self.system_prompt = self._build_system_prompt()

        if context is None:
            context = SessionContext()

        # Ensure system prompt is first message
        if not context.messages or context.messages[0].role != Role.SYSTEM:
            context.messages.insert(0, Message(role=Role.SYSTEM, content=self.system_prompt))
        else:
            # Update existing system prompt if profile changed
            context.messages[0].content = self.system_prompt

        # Append new user message
        context.add_message(Message(role=Role.USER, content=user_prompt))

        # Determine target model and provider routing
        target_model = self.model
        temperature = 0.7
        allowed_tools = None

        if active_profile:
            target_model = active_profile.model or self.model
            temperature = active_profile.temperature
            allowed_tools = active_profile.assigned_tools

            # Handle direct provider prefixes
            if active_profile.provider == "openai" and not target_model.startswith("direct/"):
                target_model = f"direct/openai/{target_model}"
            elif active_profile.provider == "anthropic" and not target_model.startswith("direct/"):
                target_model = f"direct/anthropic/{target_model}"

        iteration = 0
        final_answer = ""

        while iteration < self.max_iterations:
            iteration += 1
            tools = registry.get_openai_tools(allowed_tools)
            messages_payload = context.get_messages_for_llm()

            try:
                response = await self.client.chat_completion(
                    messages=messages_payload,
                    model=target_model,
                    tools=tools if tools else None,
                    temperature=temperature
                )
            except Exception as e:
                err_msg = f"Error communicating with LLM Provider ({target_model}): {e}"
                logger.error(err_msg)
                return f"⚠️ [LXION LLM Error]: {err_msg}"

            choice = response.get("choices", [{}])[0]
            message_data = choice.get("message", {})
            content = message_data.get("content") or ""
            tool_calls_data = message_data.get("tool_calls")

            # If there are tool calls to execute
            if tool_calls_data:
                tool_calls: List[ToolCall] = []
                for tc in tool_calls_data:
                    fn = tc.get("function", {})
                    tool_calls.append(ToolCall(
                        id=tc.get("id", ""),
                        type="function",
                        function=FunctionCall(
                            name=fn.get("name", ""),
                            arguments=fn.get("arguments", "{}")
                        )
                    ))

                # Add assistant message with tool calls to history
                context.add_message(Message(
                    role=Role.ASSISTANT,
                    content=content,
                    tool_calls=tool_calls
                ))

                # Execute all tool calls
                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_args_str = tc.function.arguments

                    if on_tool_start:
                        try:
                            parsed_args = json.loads(tool_args_str)
                        except Exception:
                            parsed_args = {"raw": tool_args_str}
                        on_tool_start(tool_name, parsed_args)

                    tool_output = await registry.execute_tool_call(
                        name=tool_name,
                        arguments_json=tool_args_str,
                        allowed_tools=allowed_tools
                    )

                    if on_tool_end:
                        on_tool_end(tool_name, tool_output)

                    # Append tool result to context
                    output_str = json.dumps(tool_output, default=str) if not isinstance(tool_output, str) else tool_output
                    context.add_message(Message(
                        role=Role.TOOL,
                        name=tool_name,
                        content=output_str,
                        tool_call_id=tc.id
                    ))
            else:
                # Final response reached
                final_answer = content
                context.add_message(Message(role=Role.ASSISTANT, content=final_answer))
                if on_token and final_answer:
                    on_token(final_answer)
                break

        return final_answer
