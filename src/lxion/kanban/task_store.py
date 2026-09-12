import json
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class KanbanTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:6]}")
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: List[str] = Field(default_factory=list)
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)  # [{"title": str, "done": bool}]
    linked_files: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

class KanbanStore:
    def __init__(self, persistence_file: Optional[Path] = None):
        self.file = (persistence_file or settings.WORKSPACE_DIR / "kanban_board.json").resolve()
        self.tasks: Dict[str, KanbanTask] = {}
        self._load()

    def _load(self):
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding="utf-8"))
                for t in data:
                    task = KanbanTask(**t)
                    self.tasks[task.id] = task
                logger.info(f"✓ Loaded {len(self.tasks)} Kanban tasks from disk.")
            except Exception as e:
                logger.warning(f"Failed to load kanban tasks: {e}")

    def _save(self):
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tasks_list = [t.model_dump() for t in self.tasks.values()]
            self.file.write_text(json.dumps(tasks_list, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save kanban board: {e}")

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        status: TaskStatus = TaskStatus.TODO,
        tags: Optional[List[str]] = None,
        linked_files: Optional[List[str]] = None
    ) -> KanbanTask:
        task = KanbanTask(
            title=title,
            description=description,
            priority=priority,
            status=status,
            tags=tags or [],
            linked_files=linked_files or []
        )
        self.tasks[task.id] = task
        self._save()
        AuditLogger.log_event("KANBAN_TASK_CREATED", "agent", {"task_id": task.id, "title": title})
        return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[TaskPriority] = None,
        add_linked_file: Optional[str] = None
    ) -> Optional[KanbanTask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        if status:
            task.status = status
        if title:
            task.title = title
        if description:
            task.description = description
        if priority:
            task.priority = priority
        if add_linked_file and add_linked_file not in task.linked_files:
            task.linked_files.append(add_linked_file)
        
        task.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        AuditLogger.log_event("KANBAN_TASK_UPDATED", "agent", {"task_id": task.id, "status": task.status.value})
        return task

    def delete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            AuditLogger.log_event("KANBAN_TASK_DELETED", "agent", {"task_id": task_id})
            return True
        return False

    def add_subtasks(self, task_id: str, subtask_titles: List[str]) -> Optional[KanbanTask]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        for title in subtask_titles:
            task.subtasks.append({"title": title, "done": False})
        task.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        return task

    def get_board(self) -> Dict[str, List[Dict[str, Any]]]:
        columns: Dict[str, List[Dict[str, Any]]] = {
            s.value: [] for s in TaskStatus
        }
        for task in self.tasks.values():
            columns[task.status.value].append(task.model_dump())
        return columns

kanban_store = KanbanStore()