from app.tools.base import BaseTool, ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        definition = tool.get_definition()
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._tools[definition.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_available(self) -> list[ToolDefinition]:
        return [tool.get_definition() for tool in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())
