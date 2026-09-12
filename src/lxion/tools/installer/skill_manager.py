import asyncio
import json
import shutil
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger
from lxion.tools.base import BaseTool
from lxion.tools.installer.manifest import SkillManifest, SkillToolDef
from lxion.tools.installer.scanner import SkillSecurityScanner, scanner

class DynamicSkillTool(BaseTool):
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], handler_func):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler_func = handler_func

    async def execute(self, **kwargs) -> Any:
        if inspect.iscoroutinefunction(self.handler_func):
            return await self.handler_func(**kwargs)
        else:
            return self.handler_func(**kwargs)

class SkillManager:
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = (skills_dir or settings.SKILLS_DIR).resolve()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.skills_dir.parent / "temp_skills"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_skills: Dict[str, Dict[str, Any]] = {}

    def _parse_manifest(self, skill_dir: Path) -> SkillManifest:
        # Check for skill.json or manifest.json
        json_file = skill_dir / "skill.json"
        if not json_file.exists():
            json_file = skill_dir / "manifest.json"
        
        if json_file.exists():
            data = json.loads(json_file.read_text(encoding="utf-8"))
            return SkillManifest(**data)

        # Check for SKILL.md frontmatter
        md_file = skill_dir / "SKILL.md"
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    lines = parts[1].strip().splitlines()
                    meta = {}
                    for line in lines:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip()] = v.strip()
                    name = meta.get("name", skill_dir.name)
                    desc = meta.get("description", "")
                    return SkillManifest(name=name, description=desc, entrypoint="main.py")

        # Fallback default manifest
        return SkillManifest(
            name=skill_dir.name,
            description=f"Skill {skill_dir.name}",
            entrypoint="main.py"
        )

    async def clone_from_github(self, repo_url: str) -> Path:
        """Clone a git repository to temp staging directory."""
        clean_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        target_dir = self.temp_dir / f"{clean_name}_{int(asyncio.get_event_loop().time())}"
        
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", repo_url, str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode('utf-8', errors='replace')}")
        return target_dir

    def scan_skill(self, skill_dir: Path) -> Dict[str, Any]:
        report = scanner.scan_directory(skill_dir)
        return report.to_dict()

    async def install_and_activate(
        self,
        skill_dir: Path,
        tool_registry,
        force_high_risk: bool = False
    ) -> Dict[str, Any]:
        """Verify, move to skills directory, load entrypoint, and register tools."""
        manifest = self._parse_manifest(skill_dir)
        sec_report = self.scan_skill(skill_dir)

        if sec_report["risk_level"] == "HIGH" and not force_high_risk:
            return {
                "success": False,
                "error": "Skill security scan reported HIGH risk. Installation blocked for safety.",
                "security_report": sec_report
            }

        # Install dependencies if specified
        if manifest.dependencies:
            for dep in manifest.dependencies:
                pip_proc = await asyncio.create_subprocess_exec(
                    "pip", "install", dep,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await pip_proc.communicate()

        # Move to official skills directory
        final_dir = self.skills_dir / manifest.name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        
        if skill_dir != final_dir:
            shutil.copytree(skill_dir, final_dir)
            if str(skill_dir).startswith(str(self.temp_dir)):
                try:
                    shutil.rmtree(skill_dir)
                except Exception:
                    pass

        # Dynamically load entrypoint module
        entrypoint_file = final_dir / manifest.entrypoint
        registered_tool_names = []

        if entrypoint_file.exists():
            spec = importlib.util.spec_from_file_location(f"lxion_skill_{manifest.name}", str(entrypoint_file))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Register declared tools
                if manifest.tools:
                    for t_def in manifest.tools:
                        if hasattr(module, t_def.handler):
                            handler = getattr(module, t_def.handler)
                            dynamic_tool = DynamicSkillTool(
                                name=t_def.name,
                                description=t_def.description,
                                parameters=t_def.parameters,
                                handler_func=handler
                            )
                            tool_registry.register_tool(dynamic_tool)
                            registered_tool_names.append(t_def.name)

        self.loaded_skills[manifest.name] = {
            "manifest": manifest.model_dump(),
            "path": str(final_dir),
            "tools": registered_tool_names,
            "security_report": sec_report,
            "active": True
        }

        AuditLogger.log_event("SKILL_INSTALLED", "agent", {
            "skill_name": manifest.name,
            "tools": registered_tool_names,
            "risk_level": sec_report["risk_level"]
        })

        return {
            "success": True,
            "skill_name": manifest.name,
            "tools_registered": registered_tool_names,
            "security_report": sec_report
        }

    def list_installed_skills(self) -> List[Dict[str, Any]]:
        results = []
        for s_dir in self.skills_dir.iterdir():
            if s_dir.is_dir() and s_dir.name != "temp_skills":
                manifest = self._parse_manifest(s_dir)
                is_active = s_dir.name in self.loaded_skills and self.loaded_skills[s_dir.name]["active"]
                results.append({
                    "name": manifest.name,
                    "description": manifest.description,
                    "version": manifest.version,
                    "tools_count": len(manifest.tools),
                    "active": is_active,
                    "path": str(s_dir)
                })
        return results

skill_manager = SkillManager()