from typing import Any, Dict, List, Optional
from lxion.tools.base import BaseTool
from lxion.memory.workspace import workspace

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file from the persistent workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str) -> str:
        return workspace.read_file(path)

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create or overwrite a file in the persistent workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace."
            },
            "content": {
                "type": "string",
                "description": "The exact text content to write."
            }
        },
        "required": ["path", "content"]
    }

    async def execute(self, path: str, content: str) -> str:
        return workspace.write_file(path, content)

class ListFilesTool(BaseTool):
    name = "list_files"
    description = "List all files in the workspace directory."
    parameters = {
        "type": "object",
        "properties": {
            "sub_dir": {
                "type": "string",
                "description": "Optional subdirectory path. Defaults to '.' (root)."
            }
        }
    }

    async def execute(self, sub_dir: str = ".") -> List[Dict[str, Any]]:
        return workspace.list_files(sub_dir)

class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file or folder from the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to delete."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str) -> str:
        return workspace.delete_file(path)

class MakeDirectoryTool(BaseTool):
    name = "make_directory"
    description = "Create a directory or folder hierarchy in the workspace (e.g. 'projects/laporan-word' or 'projects/web-app')."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative directory path inside workspace."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str) -> str:
        return workspace.create_directory(path)

class FindFilesTool(BaseTool):
    name = "find_files"
    description = "Search for files and directories matching a glob pattern (e.g. '*.docx', '*.py', 'index.*') in the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern or keyword to search for."
            },
            "sub_dir": {
                "type": "string",
                "description": "Optional subdirectory to restrict search to. Defaults to '.' (root)."
            }
        },
        "required": ["pattern"]
    }

    async def execute(self, pattern: str, sub_dir: str = ".") -> List[Dict[str, Any]]:
        return workspace.find_files(pattern=pattern, sub_dir=sub_dir)

class CreateZipTool(BaseTool):
    name = "create_zip_archive"
    description = "Compress one or more files/folders into a .zip archive inside the workspace (e.g. for packaging reports or projects)."
    parameters = {
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of relative paths to files or folders to include in the zip archive."
            },
            "zip_name": {
                "type": "string",
                "description": "Optional name for output zip file (e.g. 'laporan_final.zip')."
            }
        },
        "required": ["sources"]
    }

    async def execute(self, sources: List[str], zip_name: Optional[str] = None) -> Dict[str, Any]:
        return workspace.create_zip(sources=sources, zip_name=zip_name)

class SendFileToChannelTool(BaseTool):
    name = "send_file_to_channel"
    description = "Send a file or .zip archive from the workspace directly as a document to the user on Telegram or WhatsApp."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path of the file or zip in workspace to deliver."
            },
            "caption": {
                "type": "string",
                "description": "Optional message or caption accompanying the document."
            },
            "channel": {
                "type": "string",
                "enum": ["telegram", "whatsapp", "auto"],
                "description": "Target channel. Defaults to 'auto'."
            }
        },
        "required": ["file_path"]
    }

    async def execute(self, file_path: str, caption: str = "", channel: str = "auto") -> Dict[str, Any]:
        from lxion.channels.bus import message_bus, ChannelType, OutboundMessage
        target = workspace._resolve_safe_path(file_path)
        if not target.exists():
            return {"success": False, "error": f"File '{file_path}' not found in workspace."}
        
        target_channel = ChannelType.TELEGRAM
        if channel == "whatsapp":
            target_channel = ChannelType.WHATSAPP

        out = OutboundMessage(
            channel=target_channel,
            recipient_id="default",
            text=caption or f"Berikut file yang Anda minta: {target.name}",
            metadata={"file_path": file_path, "is_document": True, "filename": target.name}
        )
        await message_bus.send_outbound(out)
        return {
            "success": True,
            "message": f"File '{file_path}' successfully sent to {target_channel.value}.",
            "file_path": file_path,
            "size_bytes": target.stat().st_size
        }

class WorkspaceOpsTool(BaseTool):
    name = "workspace_ops"
    description = (
        "Unified file system and workspace management operations. Supported actions: "
        "'list' (list directory contents), 'delete' (remove file), 'mkdir' (create folder), "
        "'find' (search files with regex/pattern), 'create_zip' (archive files into .zip), "
        "'send_file' (send document or .zip archive to Telegram or WhatsApp)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "delete", "mkdir", "find", "create_zip", "send_file"],
                "description": "Workspace operation to perform."
            },
            "path": {
                "type": "string",
                "description": "File or folder path relative to workspace (for 'delete', 'mkdir', or 'list')."
            },
            "sub_dir": {
                "type": "string",
                "description": "Subdirectory to list or search in (default '.')."
            },
            "pattern": {
                "type": "string",
                "description": "Regex or glob pattern to search for (for 'find')."
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of relative paths to zip (for 'create_zip')."
            },
            "zip_name": {
                "type": "string",
                "description": "Optional name for output zip file (for 'create_zip')."
            },
            "file_path": {
                "type": "string",
                "description": "Relative path of the file or zip to deliver (for 'send_file')."
            },
            "caption": {
                "type": "string",
                "description": "Message accompanying document delivery (for 'send_file')."
            },
            "channel": {
                "type": "string",
                "enum": ["telegram", "whatsapp", "auto"],
                "description": "Target delivery channel (for 'send_file')."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        path: Optional[str] = None,
        sub_dir: str = ".",
        pattern: Optional[str] = None,
        sources: Optional[List[str]] = None,
        zip_name: Optional[str] = None,
        file_path: Optional[str] = None,
        caption: str = "",
        channel: str = "auto",
        **kwargs
    ) -> Any:
        act = action.strip().lower()
        if act == "list":
            return workspace.list_files(sub_dir or path or ".")
        elif act == "delete":
            target = path or file_path
            if not target:
                return {"success": False, "error": "Parameter 'path' is required for 'delete' action."}
            res = workspace.delete_file(target)
            return {"success": True, "message": str(res), "path": target}
        elif act == "mkdir":
            if not path:
                return {"success": False, "error": "Parameter 'path' is required for 'mkdir' action."}
            res = workspace.create_directory(path)
            return {"success": True, "message": str(res), "path": path}
        elif act == "find":
            if not pattern:
                return {"success": False, "error": "Parameter 'pattern' is required for 'find' action."}
            return workspace.find_files(pattern, sub_dir=sub_dir)
        elif act == "create_zip":
            if not sources:
                return {"success": False, "error": "Parameter 'sources' is required for 'create_zip' action."}
            return workspace.create_zip(sources=sources, zip_name=zip_name)
        elif act == "send_file":
            delivery_path = file_path or path
            if not delivery_path:
                return {"success": False, "error": "Parameter 'file_path' is required for 'send_file' action."}
            from lxion.channels.bus import message_bus, ChannelType, OutboundMessage
            target = workspace._resolve_safe_path(delivery_path)
            if not target.exists():
                return {"success": False, "error": f"File '{delivery_path}' not found in workspace."}
            target_channel = ChannelType.TELEGRAM
            if channel == "whatsapp":
                target_channel = ChannelType.WHATSAPP
            out = OutboundMessage(
                channel=target_channel,
                recipient_id="default",
                text=caption or f"Berikut file yang Anda minta: {target.name}",
                metadata={"file_path": delivery_path, "is_document": True, "filename": target.name}
            )
            await message_bus.send_outbound(out)
            return {
                "success": True,
                "message": f"File '{delivery_path}' successfully sent to {target_channel.value}.",
                "file_path": delivery_path,
                "size_bytes": target.stat().st_size
            }
        else:
            return {"success": False, "error": f"Unknown workspace action: '{action}'. Choose: 'list', 'delete', 'mkdir', 'find', 'create_zip', 'send_file'."}