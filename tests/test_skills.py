import json
import pytest
from pathlib import Path
from lxion.tools.installer.scanner import scanner
from lxion.tools.installer.skill_manager import skill_manager
from lxion.tools.registry import registry

@pytest.mark.asyncio
async def test_security_scanner(tmp_path):
    # Safe file
    safe_file = tmp_path / "safe.py"
    safe_file.write_text("def add(a, b):\n    return a + b\n")

    report = scanner.scan_directory(tmp_path)
    assert report.risk_level == "SAFE"
    assert report.findings == []

    # Risky file
    risky_file = tmp_path / "risky.py"
    risky_file.write_text("import os\nos.system('dir')\n")

    report_risky = scanner.scan_directory(tmp_path)
    assert report_risky.risk_level in ("MEDIUM", "HIGH")
    assert len(report_risky.findings) > 0

@pytest.mark.asyncio
async def test_dynamic_skill_installation(tmp_path):
    # Create sample skill directory
    skill_dir = tmp_path / "sample_math_skill"
    skill_dir.mkdir()

    manifest_data = {
        "name": "sample_math_skill",
        "version": "1.0.0",
        "description": "A dynamic skill for advanced math",
        "entrypoint": "main.py",
        "tools": [
            {
                "name": "power_multiply",
                "description": "Calculate base raised to power then multiply by factor",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "integer"},
                        "exponent": {"type": "integer"},
                        "factor": {"type": "integer"}
                    },
                    "required": ["base", "exponent", "factor"]
                },
                "handler": "power_mult"
            }
        ]
    }
    (skill_dir / "manifest.json").write_text(json.dumps(manifest_data))

    main_py_code = """
def power_mult(base: int, exponent: int, factor: int) -> int:
    return (base ** exponent) * factor
"""
    (skill_dir / "main.py").write_text(main_py_code)

    # Install skill
    res = await skill_manager.install_and_activate(skill_dir, registry)
    assert res["success"] is True
    assert "power_multiply" in res["tools_registered"]

    # Verify tool is registered and executable in registry
    registered_tool = registry.get_tool("power_multiply")
    assert registered_tool is not None

    tool_res = await registry.execute_tool_call("power_multiply", '{"base": 2, "exponent": 3, "factor": 5}')
    assert tool_res == 40  # (2^3) * 5 = 8 * 5 = 40