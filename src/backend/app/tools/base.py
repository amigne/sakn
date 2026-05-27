from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models import ToolModule


class ToolCategory(StrEnum):
    NETWORK = "network"
    DNS = "dns"
    SECURITY = "security"


@dataclass
class ToolParameter:
    name: str
    type: str  # "string" | "integer" | "boolean" | "enum"
    label_key: str
    description_key: str
    required: bool = False
    default: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    name: str
    display_name_key: str
    description_key: str
    category: ToolCategory
    version: str
    parameters: list[ToolParameter] = field(default_factory=list)
    requires_privileges: list[str] = field(default_factory=list)


@dataclass
class ExecutionContext:
    user_id: str | None
    session_id: str
    source_ip: str
    role: str
    request_id: str


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class BaseTool:
    """Abstract base class for all tools."""

    def get_definition(self) -> ToolDefinition:
        raise NotImplementedError

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        raise NotImplementedError

    def get_result_schema(self) -> dict[str, Any]:
        return {}

    def to_api_definition(self) -> dict[str, Any]:
        d = self.get_definition()
        return {
            "name": d.name,
            "display_name_key": d.display_name_key,
            "description_key": d.description_key,
            "category": d.category.value,
            "version": d.version,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "label_key": p.label_key,
                    "description_key": p.description_key,
                    "required": p.required,
                    "default": p.default,
                    "constraints": p.constraints,
                }
                for p in d.parameters
            ],
            "enabled": True,
        }

    def to_db_model(self) -> ToolModule:
        d = self.get_definition()
        return ToolModule(
            name=d.name,
            display_name_key=d.display_name_key,
            description_key=d.description_key,
            enabled=True,
            version=d.version,
        )
