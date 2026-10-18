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
            "requires_manual_review": breaking or change_type == "unknown",
            "patch": None,
            "patch_status": "not_generated",
        })

    return plan

