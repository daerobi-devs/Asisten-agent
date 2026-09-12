import pytest
from lxion.kanban.task_store import KanbanStore, TaskStatus, TaskPriority

def test_kanban_store_lifecycle(tmp_path):
    store = KanbanStore(persistence_file=tmp_path / "kanban_test.json")

    # 1. Create task
    task = store.create_task(
        title="Deploy to Coolify",
        description="Deploy Docker Compose LXION",
        priority=TaskPriority.HIGH,
        tags=["deployment", "infra"]
    )
    assert task.status == TaskStatus.TODO
    assert task.priority == TaskPriority.HIGH

    # 2. Add subtasks breakdown
    updated = store.add_subtasks(task.id, ["Build image", "Push repo", "Check health"])
    assert len(updated.subtasks) == 3

    # 3. Update status to IN_PROGRESS and then DONE
    store.update_task(task.id, status=TaskStatus.IN_PROGRESS)
    board = store.get_board()
    assert any(t["id"] == task.id for t in board["in_progress"])

    store.update_task(task.id, status=TaskStatus.DONE, add_linked_file="docker-compose.yml")
    board_done = store.get_board()
    assert any(t["id"] == task.id for t in board_done["done"])

    # 4. Delete task
    assert store.delete_task(task.id) is True