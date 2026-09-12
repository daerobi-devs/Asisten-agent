from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class BaseTool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool action asynchronously."""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """Convert tool definition into OpenAI-compatible tool JSON."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }