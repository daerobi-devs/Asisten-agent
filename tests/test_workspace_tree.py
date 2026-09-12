import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from lxion.memory.workspace import workspace
from lxion.tools.registry import registry
from lxion.main import app

def test_workspace_folder_and_tree_operations():
    # 1. Create a project directory
    res_mkdir = workspace.create_directory("projects/test_proj/src")
    assert "created successfully" in res_mkdir

    # 2. Write file inside project
    workspace.write_file("projects/test_proj/src/main.py", "print('Hello Project')")
    workspace.write_file("projects/test_proj/README.md", "# Test Project")

    # 3. Verify get_tree contains projects/test_proj
    tree = workspace.get_tree(include_system=False)
    proj_node = next((n for n in tree if n["name"] == "projects"), None)
    assert proj_node is not None
    assert proj_node["is_dir"] is True
    
    # 4. Verify system dirs filtered by default
    assert not any(n["name"] == "whatsapp_sessions" for n in tree)
    assert not any(n["name"] == ".git" for n in tree)

    # 5. Verify find_files
    found = workspace.find_files("*.py", sub_dir="projects/test_proj")
    assert any("main.py" in f["path"] for f in found)

    # 6. Test create_zip
    zip_res = workspace.create_zip(sources=["projects/test_proj"], zip_name="test_proj.zip")
    assert zip_res["success"] is True
    assert zip_res["files_count"] >= 2
    assert Path(workspace._resolve_safe_path("test_proj.zip")).exists()

    # Clean up
    workspace.delete_file("projects/test_proj")
    workspace.delete_file("test_proj.zip")

@pytest.mark.asyncio
async def test_file_ops_tools():
    # 1. Test make_directory tool
    res = await registry.execute_tool_call("make_directory", '{"path": "reports/laporan_word"}')
    assert "created successfully" in res

    # 2. Write a mock document
    workspace.write_file("reports/laporan_word/laporan.docx", "Mock docx binary/text")

    # 3. Test find_files tool
    found = await registry.execute_tool_call("find_files", '{"pattern": "*.docx", "sub_dir": "reports"}')
    assert any("laporan.docx" in f["path"] for f in found)

    # 4. Test create_zip_archive tool
    zip_out = await registry.execute_tool_call("create_zip_archive", '{"sources": ["reports/laporan_word"], "zip_name": "laporan.zip"}')
    assert "laporan.zip" in str(zip_out)

    # 5. Test send_file_to_channel tool
    send_out = await registry.execute_tool_call("send_file_to_channel", '{"file_path": "laporan.zip", "caption": "Laporan Anda"}')
    assert "successfully sent" in str(send_out).lower() or "dispatched" in str(send_out).lower() or "true" in str(send_out).lower()

    # Clean up
    workspace.delete_file("reports")
    workspace.delete_file("laporan.zip")

def test_workspace_api_endpoints():
    client = TestClient(app)

    # 1. GET /api/workspace/files
    res = client.get("/api/workspace/files")
    assert res.status_code == 200
    data = res.json()
    assert "files" in data
    assert "tree" in data

    # 2. POST /api/workspace/folder
    f_res = client.post("/api/workspace/folder", json={"path": "projects/api_test_folder"})
    assert f_res.status_code == 200
    assert f_res.json()["status"] == "ok"

    # 3. Write file into folder
    w_res = client.post("/api/workspace/file", json={"path": "projects/api_test_folder/note.txt", "content": "API Note"})
    assert w_res.status_code == 200

    # 4. POST /api/workspace/zip
    z_res = client.post("/api/workspace/zip", json={"sources": ["projects/api_test_folder"], "zip_name": "api_test.zip"})
    assert z_res.status_code == 200
    assert z_res.json()["success"] is True

    # 5. GET /api/workspace/download
    dl_res = client.get("/api/workspace/download?path=api_test.zip")
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 0

    # 6. DELETE folder and zip
    d1 = client.delete("/api/workspace/file?path=projects/api_test_folder")
    assert d1.status_code == 200
    d2 = client.delete("/api/workspace/file?path=api_test.zip")
    assert d2.status_code == 200
