from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import shutil
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class WorkspaceManager:
    SYSTEM_DIRS = {"whatsapp_sessions", ".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"}

    def __init__(self, root_dir: Optional[Path] = None):
        self.root = (root_dir or settings.WORKSPACE_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, rel_path: str) -> Path:
        """Resolve path and ensure it stays within the workspace root sandbox."""
        clean_path = Path(rel_path).as_posix().lstrip("/\\")
        target = (self.root / clean_path).resolve()
        if not str(target).startswith(str(self.root)):
            raise PermissionError(f"Access denied: Path '{rel_path}' is outside workspace boundary.")
        return target

    def create_directory(self, rel_path: str) -> str:
        """Create a new directory (and parent directories) safely in workspace."""
        target = self._resolve_safe_path(rel_path)
        target.mkdir(parents=True, exist_ok=True)
        AuditLogger.log_event("WORKSPACE_MKDIR", "workspace", {"path": rel_path})
        return f"Directory '{rel_path}' created successfully."

    def write_file(self, rel_path: str, content: str) -> str:
        target = self._resolve_safe_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        AuditLogger.log_event("WORKSPACE_WRITE", "agent", {"path": rel_path, "bytes": len(content)})
        return f"Successfully written {len(content)} characters to '{rel_path}'."

    def read_file(self, rel_path: str) -> str:
        target = self._resolve_safe_path(rel_path)
        if not target.exists():
            raise FileNotFoundError(f"File '{rel_path}' not found in workspace.")
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def list_files(self, sub_dir: str = ".", recursive: bool = True, include_system: bool = False) -> List[Dict[str, Any]]:
        """List files in workspace, filtering system files (whatsapp_sessions, .git) by default."""
        target = self._resolve_safe_path(sub_dir)
        if not target.exists() or not target.is_dir():
            return []
        
        entries = []
        if recursive:
            for root, dirs, files in os.walk(target):
                rel_root = os.path.relpath(root, self.root)
                if not include_system:
                    dirs[:] = [d for d in dirs if d not in self.SYSTEM_DIRS and not d.startswith(".")]
                    if any(part in self.SYSTEM_DIRS or part.startswith(".") for part in Path(rel_root).parts):
                        continue
                for f in sorted(files):
                    if not include_system and f.startswith("."):
                        continue
                    f_path = Path(root) / f
                    rel_f = os.path.normpath(os.path.join(rel_root, f)).replace("\\", "/")
                    if rel_f.startswith("./"):
                        rel_f = rel_f[2:]
                    entries.append({
                        "path": rel_f,
                        "size": f_path.stat().st_size,
                        "is_dir": False,
                        "modified": int(f_path.stat().st_mtime)
                    })
        else:
            for item in sorted(target.iterdir()):
                rel = str(item.relative_to(self.root)).replace("\\", "/")
                if not include_system and (item.name in self.SYSTEM_DIRS or item.name.startswith(".")):
                    continue
                entries.append({
                    "path": rel,
                    "size": item.stat().st_size if item.is_file() else 0,
                    "is_dir": item.is_dir(),
                    "modified": int(item.stat().st_mtime)
                })
        return entries

    def find_files(self, pattern: str = "*", sub_dir: str = ".", include_system: bool = False) -> List[Dict[str, Any]]:
        """Search files matching a glob pattern or keyword."""
        target = self._resolve_safe_path(sub_dir)
        if not target.exists():
            return []
        results = []
        for p in target.rglob(pattern):
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            if not include_system:
                if any(part in self.SYSTEM_DIRS or part.startswith(".") for part in p.parts):
                    continue
            results.append({
                "path": rel,
                "name": p.name,
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0
            })
        return results

    def create_zip(self, sources: List[str], zip_name: Optional[str] = None) -> Dict[str, Any]:
        """Package multiple files or directories into a clean .zip archive."""
        import zipfile
        if not zip_name:
            if len(sources) == 1:
                base_name = Path(sources[0]).stem
                zip_name = f"{base_name}.zip"
            else:
                zip_name = "archive.zip"
        if not zip_name.endswith(".zip"):
            zip_name += ".zip"
        
        target_zip = self._resolve_safe_path(zip_name)
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        
        file_count = 0
        with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in sources:
                src_path = self._resolve_safe_path(src)
                if not src_path.exists():
                    continue
                if src_path.is_file():
                    zf.write(src_path, arcname=src_path.name)
                    file_count += 1
                elif src_path.is_dir():
                    for root, _, files in os.walk(src_path):
                        for f in files:
                            full_file = Path(root) / f
                            arcname = full_file.relative_to(src_path.parent)
                            zf.write(full_file, arcname=str(arcname).replace("\\", "/"))
                            file_count += 1
        
        size = target_zip.stat().st_size
        rel_zip_path = str(target_zip.relative_to(self.root)).replace("\\", "/")
        AuditLogger.log_event("WORKSPACE_ZIP_CREATED", "workspace", {"zip_path": rel_zip_path, "files": file_count, "size": size})
        return {
            "success": True,
            "zip_path": rel_zip_path,
            "files_count": file_count,
            "size_bytes": size,
            "message": f"Successfully created zip archive '{rel_zip_path}' containing {file_count} files ({size} bytes)."
        }

    def get_tree(self, sub_dir: str = ".", include_system: bool = False) -> List[Dict[str, Any]]:
        """Return hierarchical directory tree for navigation in UI."""
        base_dir = self._resolve_safe_path(sub_dir)
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        def build_node(path: Path) -> Optional[Dict[str, Any]]:
            name = path.name
            rel_path = str(path.relative_to(self.root)).replace("\\", "/")
            if not include_system:
                if name in self.SYSTEM_DIRS or any(part in self.SYSTEM_DIRS for part in path.parts):
                    return None
            if path.is_dir():
                children = []
                try:
                    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        node = build_node(child)
                        if node:
                            children.append(node)
                except PermissionError:
                    pass
                return {
                    "name": name,
                    "path": rel_path,
                    "is_dir": True,
                    "children": children
                }
            else:
                return {
                    "name": name,
                    "path": rel_path,
                    "is_dir": False,
                    "size": path.stat().st_size,
                    "modified": int(path.stat().st_mtime)
                }

        tree = []
        for item in sorted(base_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            n = build_node(item)
            if n:
                tree.append(n)
        return tree

    def delete_file(self, rel_path: str) -> str:
        target = self._resolve_safe_path(rel_path)
        if target.exists():
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            AuditLogger.log_event("WORKSPACE_DELETE", "agent", {"path": rel_path})
            return f"Deleted '{rel_path}'."
        return f"File '{rel_path}' did not exist."

workspace = WorkspaceManager()