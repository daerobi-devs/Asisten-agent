import pytest
from lxion.memory.workspace import workspace
from lxion.memory.git_versioning import workspace_git

@pytest.mark.asyncio
async def test_workspace_git_workflow():
    # 1. Write file
    workspace.write_file("git_test_script.py", "print('Version 1')\n")
    
    # 2. Check status
    status = await workspace_git.status()
    assert status.get("exit_code") == 0

    # 3. Commit
    commit_res = await workspace_git.commit("feat: initial version 1")
    assert commit_res.get("exit_code") == 0

    # 4. Modify file
    workspace.write_file("git_test_script.py", "print('Version 2 - Updated')\n")
    diff = await workspace_git.diff()
    assert "Version 2 - Updated" in diff

    # 5. Commit second version
    await workspace_git.commit("feat: updated to version 2")

    # 6. Check history
    history = await workspace_git.history(limit=5)
    assert len(history) >= 2
    assert any("version 2" in c["message"] for c in history)