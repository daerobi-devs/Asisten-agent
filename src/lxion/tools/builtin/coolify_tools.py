from typing import Dict, Any, List
from lxion.tools.base import BaseTool
from lxion.companion.coolify_client import coolify_client

class CoolifyDeployTool(BaseTool):
    name = "coolify_deploy"
    description = "Trigger instant automated deployment of an application on Coolify via REST API."
    parameters = {
        "type": "object",
        "properties": {
            "app_uuid": {
                "type": "string",
                "description": "The UUID of the application on Coolify to deploy."
            }
        },
        "required": ["app_uuid"]
    }

    async def execute(self, app_uuid: str, **kwargs) -> Dict[str, Any]:
        return await coolify_client.trigger_deploy(app_uuid)

class CoolifyListAppsTool(BaseTool):
    name = "coolify_list_apps"
    description = "List applications, services, and containers configured in your Coolify dashboard."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        return await coolify_client.list_applications()

class CoolifyManagerTool(BaseTool):
    name = "coolify_manager"
    description = (
        "Unified Coolify DevOps & cloud deployment manager. Supported actions: "
        "'list_apps' (view all applications and containers), "
        "'deploy' (trigger automated redeployment of an application)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_apps", "deploy"],
                "description": "Coolify operation to perform."
            },
            "app_uuid": {
                "type": "string",
                "description": "The UUID of the application on Coolify (for 'deploy')."
            }
        },
        "required": ["action"]
    }

    async def execute(self, action: str, app_uuid: Optional[str] = None, **kwargs) -> Any:
        from typing import Optional
        act = action.strip().lower()
        if act == "list_apps":
            return await coolify_client.list_applications()
        elif act == "deploy":
            if not app_uuid:
                return {"success": False, "error": "Parameter 'app_uuid' is required for 'deploy' action."}
            return await coolify_client.trigger_deploy(app_uuid)
        else:
            return {"success": False, "error": f"Unknown coolify action: '{action}'. Choose: 'list_apps', 'deploy'."}