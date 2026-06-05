import pytest

from app.tools.base import ToolCategory, ToolDefinition
from app.tools.secret_generator import SecretGeneratorTool


class TestToolDefinitionBackend:
    """Verify the backend flag in ToolDefinition and to_api_definition()."""

    def test_default_backend_true(self):
        """ToolDefinition defaults backend=True for backward compatibility."""
        d = ToolDefinition(
            name="test",
            display_name_key="t.name",
            description_key="t.desc",
            category=ToolCategory.NETWORK,
            version="1.0",
        )
        assert d.backend is True

    def test_explicit_backend_false(self):
        """ToolDefinition accepts backend=False."""
        d = ToolDefinition(
            name="test",
            display_name_key="t.name",
            description_key="t.desc",
            category=ToolCategory.NETWORK,
            version="1.0",
            backend=False,
        )
        assert d.backend is False

    def test_to_api_definition_includes_backend(self):
        """to_api_definition() exposes the backend flag."""
        tool = SecretGeneratorTool()
        api_def = tool.to_api_definition()
        assert "backend" in api_def
        assert api_def["backend"] is False


class TestSecretGeneratorTool:
    """Unit tests for SecretGeneratorTool."""

    def test_definition_name(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        assert d.name == "secret_generator"

    def test_definition_backend_false(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        assert d.backend is False

    def test_definition_category(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        assert d.category == ToolCategory.SECURITY

    def test_definition_version(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        assert d.version == "1.0.0"

    def test_definition_parameters(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        assert len(d.parameters) == 7
        param_names = [p.name for p in d.parameters]
        assert "length" in param_names
        assert "uppercase" in param_names
        assert "lowercase" in param_names
        assert "digits" in param_names
        assert "symbols" in param_names
        assert "exclude_similar" in param_names
        assert "custom_charset" in param_names

    def test_length_parameter_constraints(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        length_param = next(p for p in d.parameters if p.name == "length")
        assert length_param.type == "integer"
        assert length_param.default == 32
        assert length_param.constraints == {"min": 8, "max": 1024}

    def test_custom_charset_constraints(self):
        tool = SecretGeneratorTool()
        d = tool.get_definition()
        cs_param = next(p for p in d.parameters if p.name == "custom_charset")
        assert cs_param.type == "string"
        assert cs_param.default == ""
        assert cs_param.constraints == {"max_length": 128}

    def test_api_definition_structure(self):
        tool = SecretGeneratorTool()
        api_def = tool.to_api_definition()
        assert api_def["name"] == "secret_generator"
        assert api_def["category"] == "security"
        assert api_def["backend"] is False
        assert api_def["version"] == "1.0.0"
        assert "display_name_key" in api_def
        assert "description_key" in api_def
        assert "parameters" in api_def

    async def test_execute_raises_not_implemented_error(self):
        """execute() is not overridden (ADR-017 §3.3) and raises NotImplementedError.

        The base BaseTool.execute() raises it as a safety net; it is never
        called server-side because the endpoint's backend=False guard returns
        405 first.
        """
        tool = SecretGeneratorTool()
        from app.tools.base import ExecutionContext

        ctx = ExecutionContext(
            user_id=None,
            session_id="s",
            source_ip="127.0.0.1",
            role="visitor",
            request_id="r",
        )
        with pytest.raises(NotImplementedError):
            await tool.execute({}, ctx)

    def test_has_settings_false(self):
        assert SecretGeneratorTool.has_settings is False

    def test_has_status_false(self):
        assert SecretGeneratorTool.has_status is False
