from app.tools.base import (
    BaseTool,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)


class SecretGeneratorTool(BaseTool):
    """Frontend-only tool: generates random secrets/passwords in the browser.

    The backend never executes this tool — it only exposes its definition
    so the frontend can render it in the sidebar and the admin panel can
    manage permissions.  The execute endpoint returns 405 for any tool
    with ``backend=False``.
    """

    has_settings: bool = False
    has_status: bool = False

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="secret_generator",
            display_name_key="tools.secret_generator.name",
            description_key="tools.secret_generator.description",
            category=ToolCategory.SECURITY,
            version="1.0.0",
            backend=False,
            parameters=[
                # Password mode
                ToolParameter(
                    name="length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_label",
                    description_key="tools.secret_generator.param_length_desc",
                    required=True,
                    default=20,
                    constraints={"min": 8, "max": 128},
                ),
                ToolParameter(
                    name="uppercase",
                    type="boolean",
                    label_key="tools.secret_generator.param_uppercase_label",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="lowercase",
                    type="boolean",
                    label_key="tools.secret_generator.param_lowercase_label",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="digits",
                    type="boolean",
                    label_key="tools.secret_generator.param_digits_label",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="symbols",
                    type="boolean",
                    label_key="tools.secret_generator.param_symbols_label",
                    required=False,
                    default=True,
                ),
                # Token mode
                ToolParameter(
                    name="token_length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_token_label",
                    description_key="tools.secret_generator.param_length_token_desc",
                    required=False,
                    default=43,
                    constraints={"min": 16, "max": 256},
                ),
                # Hex mode
                ToolParameter(
                    name="hex_length",
                    type="integer",
                    label_key="tools.secret_generator.param_length_hex_label",
                    description_key="tools.secret_generator.param_length_hex_desc",
                    required=False,
                    default=64,
                    constraints={"min": 16, "max": 512},
                ),
            ],
        )

    # execute() is intentionally NOT overridden (ADR-017 §3.3): the base
    # BaseTool.execute() already raises NotImplementedError, and the execute
    # endpoint's backend=False guard returns 405 before it is ever reached.
