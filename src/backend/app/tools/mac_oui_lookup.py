"""MAC OUI Lookup tool — instant tool backend.

Receives a list of normalised OUI/MAC strings, validates in zero-trust mode,
performs a single-query longest-prefix lookup against the local IEEE database,
and returns structured results with ambiguity detection.

Architecture: ADR-014 §2.1, §2.7 (zero-trust backend, no regex extraction).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.api.errors import AppError
from app.database import async_session_factory, is_db_available
from app.monitoring.metrics import (
    mac_oui_lookup_duration_seconds,
    mac_oui_lookup_requests_total,
)
from app.tools.base import BaseTool, ExecutionContext, ToolCategory, ToolDefinition, ToolResult
from app.tools.mac_oui_lookup_service import lookup_batch
from app.tools.mac_oui_validator import validate_batch

logger = logging.getLogger(__name__)

# Default batch size cap (configurable via GlobalSetting key).
DEFAULT_BATCH_MAX_SIZE = 2000


class MacOuiLookupTool(BaseTool):
    """MAC OUI Lookup — resolve MAC/OUI prefixes to vendor organizations."""

    # Metadata carried on the class for seed / introspection.
    # These are consumed by main.py seed logic for the ToolModule row.
    has_settings: bool = True
    has_status: bool = True

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="mac_oui",
            display_name_key="tools.mac_oui.name",
            description_key="tools.mac_oui.description",
            category=ToolCategory.NETWORK,
            version="1.0.0",
            parameters=[],  # no user-editable parameters — body is {"ouis": [...]}
        )

    # ------------------------------------------------------------------
    # Request validation (structural — raises AppError → 422 on failure)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_request_body(params: dict[str, Any]) -> list[str]:
        """Validate the incoming JSON structure and return the ``ouis`` list.

        Raises:
            AppError(422, "VALIDATION_ERROR"): if ``ouis`` is missing, not a
                list, or contains non-string items.
        """
        if not isinstance(params, dict):
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message_key="errors.validation",
                message="Request body must be a JSON object.",
            )

        ouis = params.get("ouis")
        if ouis is None:
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message_key="errors.validation",
                message="The 'ouis' field is required.",
                details={
                    "fields": {
                        "ouis": {
                            "message_key": "errors.field_required",
                            "message": "This field is required.",
                        }
                    }
                },
            )

        if not isinstance(ouis, list):
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message_key="errors.validation",
                message="The 'ouis' field must be an array of strings.",
            )

        # Verify all elements are strings (non-string items → 422)
        for i, item in enumerate(ouis):
            if not isinstance(item, str):
                raise AppError(
                    status_code=422,
                    code="VALIDATION_ERROR",
                    message_key="errors.validation",
                    message=f"The 'ouis' array must contain only strings. Item at index {i} is {type(item).__name__}.",
                )

        return ouis

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, params: dict[str, Any], context: ExecutionContext) -> ToolResult:
        """Execute the MAC OUI lookup tool.

        Structural validation (missing ``ouis``, wrong types) raises
        ``AppError(422)`` which FastAPI converts to HTTP 422.

        Batch-size exceeded raises ``AppError(422, "MAC_OUI_TOO_MANY_INPUTS")``.

        Individual invalid entries are returned in ``rejected[]`` with
        HTTP 200 — never 422 per ADR-014 §2.7.
        """
        start = time.monotonic()

        # --- Structural validation (raises AppError → 422 on failure) ---------
        ouis = self._validate_request_body(params)

        # --- Batch size limit -------------------------------------------------
        max_size = DEFAULT_BATCH_MAX_SIZE
        try:
            if is_db_available():
                from sqlalchemy import select

                from app.models.preferences import GlobalSetting

                async with async_session_factory() as db:
                    row = await db.execute(
                        select(GlobalSetting).where(
                            GlobalSetting.key == "module.mac_oui.MAC_OUI_BACKEND_BATCH_MAX_SIZE"
                        )
                    )
                    setting = row.scalar_one_or_none()
                    if setting is not None:
                        max_size = int(setting.value)
        except Exception:
            logger.debug(
                "Could not load MAC_OUI_BACKEND_BATCH_MAX_SIZE, using default %s",
                DEFAULT_BATCH_MAX_SIZE,
                exc_info=True,
            )

        if len(ouis) > max_size:
            raise AppError(
                status_code=422,
                code="MAC_OUI_TOO_MANY_INPUTS",
                message_key="errors.mac_oui_too_many_inputs",
                message=f"Too many inputs. Maximum is {max_size}.",
                details={"max": max_size},
            )

        # --- Zero-trust validation --------------------------------------------
        validated, rejected = validate_batch(ouis)

        # --- Database lookup --------------------------------------------------
        results = []
        if validated and is_db_available():
            try:
                async with async_session_factory() as db:
                    results = await lookup_batch(db, validated)
            except Exception:
                logger.exception("MAC OUI lookup failed")
                duration_ms = (time.monotonic() - start) * 1000
                mac_oui_lookup_requests_total.labels(result="error").inc()
                return ToolResult(
                    success=False,
                    error="errors.internal_error",
                    duration_ms=duration_ms,
                )
        elif validated and not is_db_available():
            duration_ms = (time.monotonic() - start) * 1000
            mac_oui_lookup_requests_total.labels(result="error").inc()
            return ToolResult(
                success=False,
                error="errors.internal_error",
                duration_ms=duration_ms,
            )

        # --- Serialise results ------------------------------------------------
        serialised_results = _serialise_results(results)
        serialised_rejected = _serialise_rejected(rejected)
        valid_normalized = {v.normalized for v in validated}

        duration_ms = (time.monotonic() - start) * 1000

        # Emit Prometheus metrics (ADR-015)
        hit_count = sum(1 for r in results if r.result is not None)
        miss_count = len(results) - hit_count
        if hit_count:
            mac_oui_lookup_requests_total.labels(result="hit").inc(hit_count)
        if miss_count:
            mac_oui_lookup_requests_total.labels(result="miss").inc(miss_count)
        if rejected:
            mac_oui_lookup_requests_total.labels(result="rejected").inc(len(rejected))
        mac_oui_lookup_duration_seconds.observe(duration_ms / 1000.0)

        return ToolResult(
            success=True,
            data={
                "results": serialised_results,
                "rejected": serialised_rejected,
                "parse_stats": {
                    "total_inputs": len(ouis),
                    "valid": len(validated),
                    "rejected": len(rejected),
                    "unique": len(valid_normalized),
                },
            },
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Serialisation helpers (module-level for testability)
# ---------------------------------------------------------------------------


def _serialise_results(results) -> list[dict[str, Any]]:
    """Convert LookupRow objects to JSON-serialisable dicts."""
    output = []
    for row in results:
        entry: dict[str, Any] = {
            "input": row.input,
            "oui_display": row.oui_display,
            "result": None,
            "ambiguous_extends_ma_m": row.ambiguous_extends_ma_m,
            "ambiguous_extends_ma_s": row.ambiguous_extends_ma_s,
            "history": [
                {
                    "change_type": h.change_type,
                    "previous_organization": h.previous_organization,
                    "new_organization": h.new_organization,
                    "previous_address": h.previous_address,
                    "new_address": h.new_address,
                    "detected_at": h.detected_at.isoformat(),
                }
                for h in row.history
            ],
        }
        if row.result is not None:
            entry["result"] = {
                "oui_type": row.result.oui_type,
                "organization": row.result.organization,
                "address": row.result.address,
                "first_seen": row.result.first_seen.isoformat(),
                "last_seen": row.result.last_seen.isoformat(),
            }
        output.append(entry)
    return output


def _serialise_rejected(rejected) -> list[dict[str, Any]]:
    """Convert RejectedEntry objects to JSON-serialisable dicts."""
    return [
        {
            "index": r.index,
            "sample": r.sample,
            "reason": r.reason,
        }
        for r in rejected
    ]
