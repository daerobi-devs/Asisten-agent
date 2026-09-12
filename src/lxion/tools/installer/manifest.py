from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SkillToolDef(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: str  # Function name in entrypoint file

class SkillManifest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: Optional[str] = "Unknown"
    repository: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)  # e.g. ["filesystem", "network", "shell"]
    entrypoint: str = "main.py"
    tools: List[SkillToolDef] = Field(default_factory=list)