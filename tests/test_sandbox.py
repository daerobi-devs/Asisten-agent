import pytest
from lxion.sandbox.runner import sandbox

@pytest.mark.asyncio
async def test_python_code_execution():
    code = """
def calculate():
    return sum([x * 2 for x in range(1, 6)])
print(f"RESULT={calculate()}")
"""
    result = await sandbox.execute_code("python", code)
    assert result.exit_code == 0
    assert "RESULT=30" in result.stdout
    assert result.timed_out is False
    assert result.execution_time_ms > 0

@pytest.mark.asyncio
async def test_code_timeout():
    code = """
import time
time.sleep(5)
print("done")
"""
    result = await sandbox.execute_code("python", code, timeout_seconds=1)
    assert result.timed_out is True
    assert "timed out" in result.stderr