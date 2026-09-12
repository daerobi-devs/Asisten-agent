from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.kanban.task_store import kanban_store, TaskStatus, TaskPriority

class KanbanCreateTaskTool(BaseTool):
    name = "kanban_create_task"
    description = "Create a new task on the Kanban board."
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short, clear title of the task."
            },
            "description": {
                "type": "string",
                "description": "Detailed requirements or context for the task."
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Priority level (default 'medium')."
            },
            "status": {
                "type": "string",
                "enum": ["backlog", "todo", "in_progress", "review", "done"],
                "description": "Initial column on the board (default 'todo')."
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional category tags."
            }
        },
        "required": ["title"]
    }

    async def execute(
        self,
        title: Optional[str] = None,
        description: str = "",
        priority: str = "medium",
        status: str = "todo",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        final_title = title or description[:40] or "Untitled Task"
        p = TaskPriority(priority.lower()) if priority.lower() in [e.value for e in TaskPriority] else TaskPriority.MEDIUM
        s = TaskStatus(status.lower()) if status.lower() in [e.value for e in TaskStatus] else TaskStatus.TODO
        task = kanban_store.create_task(
            title=final_title,
            description=description,
            priority=p,
            status=s,
            tags=tags or []
        )
        return {"success": True, "task": task.model_dump()}

class KanbanUpdateTaskTool(BaseTool):
    name = "kanban_update_task"
    description = "Update status, priority, or details of an existing Kanban task."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to update (e.g. 'task_a1b2c3')."
            },
            "status": {
                "type": "string",
                "enum": ["backlog", "todo", "in_progress", "review", "done"],
                "description": "Move task to this column."
            },
            "title": {"type": "string", "description": "New title."},
            "description": {"type": "string", "description": "New description."},
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Updated priority."
            },
            "add_linked_file": {
                "type": "string",
                "description": "Path to a workspace file resulting from this task."
            }
        },
        "required": ["task_id"]
    }

    async def execute(
        self,
        task_id: str,
        status: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        add_linked_file: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        s = TaskStatus(status.lower()) if status and status.lower() in [e.value for e in TaskStatus] else None
        p = TaskPriority(priority.lower()) if priority and priority.lower() in [e.value for e in TaskPriority] else None
        res = kanban_store.update_task(
            task_id=task_id,
            status=s,
            title=title,
            description=description,
            priority=p,
            add_linked_file=add_linked_file
        )
        if res:
            return {"success": True, "task": res.model_dump()}
        return {"success": False, "error": f"Task '{task_id}' not found."}

class KanbanGetBoardTool(BaseTool):
    name = "kanban_get_board"
    description = "Retrieve the complete Kanban board with all columns and current tasks."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return kanban_store.get_board()

class KanbanBreakdownTool(BaseTool):
    name = "kanban_breakdown_task"
    description = "Break down a complex Kanban task into actionable checklist subtasks."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The parent task ID."
            },
            "subtasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of subtask titles to add."
            }
        },
        "required": ["task_id", "subtasks"]
    }

    async def execute(self, task_id: str, subtasks: List[str], **kwargs) -> Dict[str, Any]:
        res = kanban_store.add_subtasks(task_id, subtasks)
        if res:
            return {"success": True, "task": res.model_dump()}
        return {"success": False, "error": f"Task '{task_id}' not found."}

class KanbanManagerTool(BaseTool):
    name = "kanban_manager"
    description = (
        "Unified agile Kanban board manager. Perform actions: "
        "'get_board' (retrieve all tasks), 'create' (create new task), "
        "'update' (change status, priority, details), or 'breakdown' (generate subtasks checklist)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_board", "create", "update", "breakdown"],
                "description": "The Kanban operation to execute."
            },
            "task_id": {
                "type": "string",
                "description": "Task ID (required for 'update' and 'breakdown')."
            },
            "title": {
                "type": "string",
                "description": "Title of the task."
            },
            "description": {
                "type": "string",
                "description": "Task context, instructions, or requirements."
            },
            "status": {
                "type": "string",
                "enum": ["backlog", "todo", "in_progress", "review", "done"],
                "description": "Column status."
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Task priority."
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category tags for the task."
            },
            "subtasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of subtask titles (for 'breakdown')."
            },
            "add_linked_file": {
                "type": "string",
                "description": "Path to a workspace file created/modified by this task."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        description: str = "",
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        subtasks: Optional[List[str]] = None,
        add_linked_file: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        act = action.strip().lower()
        if act == "get_board":
            return kanban_store.get_board()

        elif act == "create":
            final_title = title or description[:40] or "Untitled Task"
            p = TaskPriority(priority.lower()) if priority and priority.lower() in [e.value for e in TaskPriority] else TaskPriority.MEDIUM
            s = TaskStatus(status.lower()) if status and status.lower() in [e.value for e in TaskStatus] else TaskStatus.TODO
            task = kanban_store.create_task(
                title=final_title,
                description=description,
                priority=p,
                status=s,
                tags=tags or []
            )
            return {"success": True, "task": task.model_dump()}

        elif act == "update":
            if not task_id:
                return {"success": False, "error": "Parameter 'task_id' is required for 'update' action."}
            s = TaskStatus(status.lower()) if status and status.lower() in [e.value for e in TaskStatus] else None
            p = TaskPriority(priority.lower()) if priority and priority.lower() in [e.value for e in TaskPriority] else None
            res = kanban_store.update_task(
                task_id=task_id,
                status=s,
                title=title,
                description=description,
                priority=p,
                add_linked_file=add_linked_file
            )
            if res:
                return {"success": True, "task": res.model_dump()}
            return {"success": False, "error": f"Task '{task_id}' not found."}

        elif act == "breakdown":
            if not task_id:
                return {"success": False, "error": "Parameter 'task_id' is required for 'breakdown' action."}
            res = kanban_store.add_subtasks(task_id, subtasks or [])
            if res:
                return {"success": True, "task": res.model_dump()}
            return {"success": False, "error": f"Task '{task_id}' not found."}

        else:
            return {"success": False, "error": f"Unknown Kanban action: '{action}'. Choose: 'get_board', 'create', 'update', 'breakdown'."}