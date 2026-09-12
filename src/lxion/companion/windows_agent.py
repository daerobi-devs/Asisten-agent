import os
import sys
import platform
import io
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(
    title="LXION Windows Laptop Companion",
    version="0.3.0",
    description="Lightweight local daemon running on Windows laptop via Tailscale"
)

AUTH_TOKEN = os.getenv("COMPANION_AUTH_TOKEN", "lxion_tailscale_secret_2026")

USER_HOME = Path.home()
ALLOWED_ROOTS = [
    USER_HOME / "Documents",
    USER_HOME / "Desktop",
    USER_HOME / "Downloads",
    Path("D:/ASISTENPRIBADI"),
    Path("D:/ASISTENPRIBADI/workspace")
]

ALLOWED_COMMANDS = [
    "dir", "echo", "type", "git", "python", "ipconfig", "systeminfo", "tasklist"
]

def verify_token(authorization: Optional[str]):
    if not AUTH_TOKEN:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid Companion Token")

def verify_path_allowed(target_path: Path) -> Path:
    resolved = target_path.resolve()
    is_allowed = any(
        str(resolved).lower().startswith(str(root.resolve()).lower())
        for root in ALLOWED_ROOTS
    )
    if not is_allowed:
        raise HTTPException(status_code=403, detail=f"Access denied: Path '{resolved}' is not in whitelisted folders.")
    return resolved

class PathRequest(BaseModel):
    path: str

class ExecRequest(BaseModel):
    command: str
    timeout_seconds: int = 30

@app.get("/health")
@app.get("/status")
async def get_status(authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    try:
        import psutil
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("C:\\").percent
    except Exception:
        cpu, ram, disk = 0.0, 0.0, 0.0

    return {
        "status": "online",
        "device": platform.node(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_c_percent": disk,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/screenshot")
async def capture_screenshot(authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    from PIL import Image, ImageDraw
    
    # Try capturing active screen
    img = None
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=False)
    except Exception:
        # Fallback for headless / locked session: render diagnostic status frame
        img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), f"LXION Windows Companion - Screen Capture", fill=(99, 102, 241))
        draw.text((50, 90), f"Host: {platform.node()} | OS: {platform.system()} {platform.release()}", fill=(203, 213, 225))
        draw.text((50, 130), f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}", fill=(148, 163, 184))
        draw.text((50, 170), "Notice: Active display session in headless/background mode.", fill=(251, 191, 36))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

@app.post("/files/list")
async def list_files(req: PathRequest, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    target = verify_path_allowed(Path(req.path))
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    items = []
    for entry in target.iterdir():
        items.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "size": entry.stat().st_size if entry.is_file() else 0
        })
    return {"path": str(target), "items": items[:100]}

@app.post("/files/read")
async def read_file(req: PathRequest, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    target = verify_path_allowed(Path(req.path))
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": str(target), "content": content[:20000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/exec")
async def execute_command(req: ExecRequest, authorization: Optional[str] = Header(None)):
    verify_token(authorization)
    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Empty command")

    # Anti-command-chaining guard: reject shell separators and redirection
    dangerous_operators = [";", "&", "|", "`", "$(", "${", ">", "<", "\n"]
    if any(op in cmd for op in dangerous_operators):
        raise HTTPException(status_code=403, detail="Command execution denied: shell chaining/redirection operators are forbidden.")

    cmd_first_word = cmd.split()[0].lower()
    if cmd_first_word not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=403, detail=f"Command '{cmd_first_word}' is not in allowed whitelist: {ALLOWED_COMMANDS}")

    import subprocess
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=float(req.timeout_seconds)
        )
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9099)