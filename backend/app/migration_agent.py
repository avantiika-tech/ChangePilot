
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
def _build_recommendation(change: dict[str, Any]) -> str:
    """Build a migration recommendation using the change evidence."""
    change_type = change.get("type", "unknown")
    evidence = change.get("evidence", {})

    if change_type == "response_property_removed":
        property_name = evidence.get("property", "unknown")
        status_code = evidence.get("status_code", "unknown")

        return (
            f"Response property `{property_name}` was removed from "
            f"HTTP status {status_code}. Find and update client code "
            "that reads this property, then verify behavior against "
            "the new API contract."
        )

    if change_type == "response_property_type_changed":
        property_name = evidence.get("property", "unknown")
        old_type = evidence.get("old_type", "unknown")
        new_type = evidence.get("new_type", "unknown")

        return (
            f"Response property `{property_name}` changed from "
            f"`{old_type}` to `{new_type}`. Update affected client "
            "code to handle the new type and verify the conversion "
            "against actual API responses."
        )

    if change_type == "response_status_removed":
        status_code = evidence.get("status_code", "unknown")

        return (
            f"HTTP response status {status_code} was removed. Review "
            "client handling for this status and confirm the supported "
            "response behavior in the new API contract."
        )

    if change_type == "added_parameter":
        parameter = evidence.get("parameter")
        location = evidence.get("in", "unknown")
        is_required = evidence.get(
            "required",
            evidence.get("new_required"),
        )

        if is_required is True:
            base = (
                f"The required {location} parameter "
                f"`{parameter}` was added."
                if parameter
                else f"A required {location} parameter was added."
            )
            return (
                f"{base} Supply a valid value from application data or "
                "configuration, then verify the request against the new "
                "API contract."
            )

        if is_required is False:
            base = (
                f"The optional {location} parameter `{parameter}` was added."
                if parameter
                else f"An optional {location} parameter was added."
            )
            return (
                f"{base} Include it only if the application needs it, "
                "and verify the request against the new API contract."
            )

    return MIGRATION_GUIDANCE.get(
        change_type,
        "Review the API change and update affected calls manually.",
    )


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
            recommendation = _build_recommendation(change)

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
