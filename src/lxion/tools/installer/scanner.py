import ast
import re
from pathlib import Path
from typing import List, Dict, Any

RISKY_PATTERNS = [
    (r"subprocess\.Popen\(.*shell\s*=\s*True", "Shell execution with shell=True"),
    (r"os\.system\(", "Direct os.system call"),
    (r"eval\(|exec\(", "Dynamic code evaluation (eval/exec)"),
    (r"socket\.socket\(", "Raw socket network connection"),
    (r"shutil\.rmtree\(['\"]\/['\"]\)", "Root deletion attempt"),
    (r"base64\.b64decode\(.*exec\(", "Obfuscated payload execution"),
]

class SecurityReport:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.findings: List[Dict[str, Any]] = []
        self.risk_level: str = "SAFE"  # SAFE, LOW, MEDIUM, HIGH

    def add_finding(self, file_path: str, severity: str, message: str, line_no: int = 0):
        self.findings.append({
            "file": file_path,
            "severity": severity,
            "message": message,
            "line": line_no
        })
        if severity == "HIGH":
            self.risk_level = "HIGH"
        elif severity == "MEDIUM" and self.risk_level != "HIGH":
            self.risk_level = "MEDIUM"
        elif severity == "LOW" and self.risk_level not in ("HIGH", "MEDIUM"):
            self.risk_level = "LOW"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "total_findings": len(self.findings),
            "findings": self.findings
        }

class SkillSecurityScanner:
    @staticmethod
    def scan_directory(directory: Path) -> SecurityReport:
        report = SecurityReport(directory)
        
        for py_file in directory.rglob("*.py"):
            rel_path = py_file.relative_to(directory).as_posix()
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                
                # Regex pattern matching
                for pattern, desc in RISKY_PATTERNS:
                    matches = list(re.finditer(pattern, content))
                    for m in matches:
                        line_no = content[:m.start()].count("\n") + 1
                        severity = "HIGH" if "payload" in desc or "Root" in desc else "MEDIUM"
                        report.add_finding(rel_path, severity, desc, line_no)

                # AST Parsing check
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name in ("pty", "ctypes", "winreg"):
                                    report.add_finding(rel_path, "LOW", f"Import of low-level system module: {alias.name}", node.lineno)
                except SyntaxError as se:
                    report.add_finding(rel_path, "MEDIUM", f"Syntax error in python file: {se.msg}", se.lineno or 0)

            except Exception as e:
                report.add_finding(rel_path, "LOW", f"Could not read file: {e}")

        return report

scanner = SkillSecurityScanner()