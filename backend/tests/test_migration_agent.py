from app.migration_agent import generate_migration_plan


def test_breaking_change_generates_recommendation():
    matches = [{
        "change": {
            "type": "parameter_became_required",
            "severity": "high",
            "breaking": True,
            "method": "GET",
            "path": "/users",
            "message": "Parameter 'limit' is now required.",
            "evidence": {"parameter": "limit"},
        },
        "affected_calls": [
            {"file": "client.py", "line": 10, "call": "requests.get"}
        ],
    }]

    plan = generate_migration_plan(matches)

    assert len(plan) == 1
    assert plan[0]["breaking"] is True
    assert plan[0]["affected_call_count"] == 1
    assert "required" in plan[0]["recommendation"]
    assert plan[0]["patch"] is None
    assert plan[0]["patch_status"] == "not_generated"


def test_non_breaking_change_does_not_require_manual_review():
    matches = [{
        "change": {
            "type": "added_endpoint",
            "severity": "info",
            "breaking": False,
            "method": "GET",
            "path": "/health",
            "message": "GET /health was added.",
            "evidence": {},
        },
        "affected_calls": [],
    }]

    plan = generate_migration_plan(matches)

    assert len(plan) == 1
    assert plan[0]["breaking"] is False
    assert plan[0]["requires_manual_review"] is False
    assert plan[0]["affected_call_count"] == 0


def test_empty_input_returns_empty_plan():
    assert generate_migration_plan([]) == []
