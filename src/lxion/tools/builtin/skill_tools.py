from pathlib import Path
from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.tools.installer.skill_manager import skill_manager
from lxion.core.logger import logger

class InstallSkillTool(BaseTool):
    name = "install_skill"
    description = "Install a skill from a GitHub repository URL or a local folder path with automated security scanning and tool activation."
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "GitHub repository URL (e.g. 'https://github.com/org/repo') or local folder path."
            },
            "force_high_risk": {
                "type": "boolean",
                "description": "Whether to bypass high-risk security scan blocks (default false)."
            }
        },
        "required": ["source"]
    }

    async def execute(self, source: str, force_high_risk: bool = False, **kwargs) -> Dict[str, Any]:
        from lxion.tools.registry import registry
        try:
            if source.startswith("http://") or source.startswith("https://") or source.startswith("git@"):
                skill_dir = await skill_manager.clone_from_github(source)
            else:
                skill_dir = Path(source).resolve()
                if not skill_dir.exists():
                    return {"success": False, "error": f"Path '{source}' does not exist."}

            res = await skill_manager.install_and_activate(
                skill_dir=skill_dir,
                tool_registry=registry,
                force_high_risk=force_high_risk
            )
            return res
        except Exception as e:
            logger.error(f"Failed to install skill from {source}: {e}")
            return {"success": False, "error": str(e)}

class ListSkillsTool(BaseTool):
    name = "list_skills"
    description = "List all installed skills in the agent skill registry."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        return skill_manager.list_installed_skills()

class ScanSkillTool(BaseTool):
    name = "scan_skill"
    description = "Run security and manifest analysis on a skill directory without installing it."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to skill directory."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str, **kwargs) -> Dict[str, Any]:
        target = Path(path).resolve()
        if not target.exists():
            return {"error": f"Path '{path}' does not exist."}
        return skill_manager.scan_skill(target)

class SkillManagerTool(BaseTool):
    name = "skill_manager"
    description = (
        "Unified skill registry & installer manager. Supported actions: "
        "'list' (show all installed skills), 'install' (clone & install skill from GitHub/path), "
        "'scan' (security and manifest analysis of skill directory)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "install", "scan"],
                "description": "Skill operation to perform."
            },
            "source": {
                "type": "string",
                "description": "GitHub repository URL or local folder path (for 'install')."
            },
            "path": {
                "type": "string",
                "description": "Local path to skill directory (for 'scan')."
            },
            "force_high_risk": {
                "type": "boolean",
                "description": "Whether to bypass high-risk security scan blocks (for 'install', default false)."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        source: Optional[str] = None,
        path: Optional[str] = None,
        force_high_risk: bool = False,
        **kwargs
    ) -> Any:
        act = action.strip().lower()
        if act == "list":
            return skill_manager.list_installed_skills()
        elif act == "install":
            if not source:
                return {"success": False, "error": "Parameter 'source' is required for 'install' action."}
            from lxion.tools.registry import registry
            try:
                if source.startswith("http://") or source.startswith("https://") or source.startswith("git@"):
                    skill_dir = await skill_manager.clone_from_github(source)
                else:
                    skill_dir = Path(source).resolve()
                    if not skill_dir.exists():
                        return {"success": False, "error": f"Path '{source}' does not exist."}

                res = await skill_manager.install_and_activate(
                    skill_dir=skill_dir,
                    tool_registry=registry,
                    force_high_risk=force_high_risk
                )
                return res
            except Exception as e:
                logger.error(f"Failed to install skill from {source}: {e}")
                return {"success": False, "error": str(e)}
        elif act == "scan":
            target_path = path or source
            if not target_path:
                return {"success": False, "error": "Parameter 'path' is required for 'scan' action."}
            target = Path(target_path).resolve()
            if not target.exists():
                return {"success": False, "error": f"Path '{target_path}' does not exist."}
            return skill_manager.scan_skill(target)
        else:
            return {"success": False, "error": f"Unknown skill action: '{action}'. Choose: 'list', 'install', 'scan'."}