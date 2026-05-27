import pytest

from app.tools.base import BaseTool, ToolCategory, ToolDefinition
from app.tools.registry import ToolRegistry


class FakeTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="fake",
            display_name_key="tools.fake.name",
            description_key="tools.fake.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
        )


class FakeTool2(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="fake2",
            display_name_key="tools.fake2.name",
            description_key="tools.fake2.description",
            category=ToolCategory.DNS,
            version="1.0.0",
        )


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register(tool)
        assert registry.get("fake") is tool

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(FakeTool())

    def test_get_missing_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_list_available(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        registry.register(FakeTool2())
        defs = registry.list_available()
        assert len(defs) == 2
        names = [d.name for d in defs]
        assert "fake" in names
        assert "fake2" in names

    def test_list_names(self):
        registry = ToolRegistry()
        registry.register(FakeTool())
        registry.register(FakeTool2())
        assert set(registry.list_names()) == {"fake", "fake2"}
