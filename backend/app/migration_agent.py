
from typing import Any


MIGRATION_GUIDANCE = {
    "removed_endpoint": (
        "The endpoint was removed. Find a supported replacement in the new "
        "API specification and update the call. Do not guess a replacement."
    ),
    "removed_parameter": (
        "The parameter was removed from the API contract. Remove it from "
        "the request if the client still sends it, then check related logic."
    ),
    "added_parameter": (
        "A parameter was added. Check whether it is required. If required, "
        "supply a valid value; if optional, include it only when appropriate."
    ),
    "parameter_became_required": (
        "The parameter is now required. Update the request to supply a valid "
        "value from configuration or application data."
    ),
    "parameter_type_changed": (
        "The parameter type changed. Inspect the expected new type and "
        "convert the value safely; do not assume a conversion is lossless."
    ),
}


PATCH_ACTIONS = {
    "removed_endpoint": "manual_replacement_required",
    "removed_parameter": "inspect_and_remove_parameter",
    "added_parameter": "inspect_parameter_requirements",
    "parameter_became_required": "supply_value_from_application_data",
    "parameter_type_changed": "inspect_and_convert_value",
}


def generate_migration_plan(
    change_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create evidence-based migration recommendations for API changes."""
    plan = []

    for item in change_matches:
        change = item.get("change", {})
        change_type = change.get("type", "unknown")
        breaking = change.get("breaking", False)
        affected_calls = item.get("affected_calls", [])

        if not breaking:
            recommendation = (
                "This change is marked non-breaking. Review it for relevance; "
                "a migration may not be necessary."
            )
        else:
            recommendation = MIGRATION_GUIDANCE.get(
                change_type,
                "Review the API change and update affected calls manually.",
            )

        patch_action = PATCH_ACTIONS.get(change_type, "manual_review_required")

        plan.append({
            "change_type": change_type,
            "severity": change.get("severity", "unknown"),
            "breaking": breaking,
            "method": change.get("method"),
            "path": change.get("path"),
            "summary": change.get("message", "No summary provided."),
            "evidence": change.get("evidence", {}),
            "affected_calls": affected_calls,
            "affected_call_count": len(affected_calls),
            "recommendation": recommendation,
            "requires_manual_review": (
                breaking or change_type == "unknown"
            ),
            "patch": None,
            "patch_status": "not_generated",
            "patch_action": patch_action,
        })

    return plan
