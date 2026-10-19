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


def test_removed_response_property_generates_manual_review_recommendation():
    matches = [{
        "change": {
            "type": "response_property_removed",
            "severity": "high",
            "breaking": True,
            "method": "GET",
            "path": "/users",
            "message": "Response property 'email' was removed.",
            "evidence": {
                "property": "email",
                "status_code": "200",
                "old_schema": {"type": "string"},
                "new_schema": None,
            },
        },
        "affected_calls": [
            {
                "file": "client.py",
                "line": 10,
                "call": "requests.get",
            }
        ],
    }]

    plan = generate_migration_plan(matches)

    assert len(plan) == 1
    assert plan[0]["breaking"] is True
    assert plan[0]["affected_call_count"] == 1
    assert plan[0]["requires_manual_review"] is True
    assert plan[0]["evidence"]["property"] == "email"
    assert plan[0]["patch"] is None
    assert plan[0]["patch_status"] == "not_generated"

def test_removed_response_property_has_actionable_recommendation():
    matches = [{
        "change": {
            "type": "response_property_removed",
            "severity": "high",
            "breaking": True,
            "method": "GET",
            "path": "/users",
            "message": "Response property 'email' was removed.",
            "evidence": {
                "property": "email",
                "status_code": "200",
            },
        },
        "affected_calls": [],
    }]

    plan = generate_migration_plan(matches)

    assert "email" in plan[0]["recommendation"]
    assert "200" in plan[0]["recommendation"]
    assert "client code" in plan[0]["recommendation"]
    assert plan[0]["requires_manual_review"] is True


def test_removed_response_status_has_actionable_recommendation():
    matches = [{
        "change": {
            "type": "response_status_removed",
            "severity": "high",
            "breaking": True,
            "method": "GET",
            "path": "/users",
            "message": "Response status code '404' was removed.",
            "evidence": {"status_code": "404"},
        },
        "affected_calls": [],
    }]

    plan = generate_migration_plan(matches)

    assert "404" in plan[0]["recommendation"]
    assert "response behavior" in plan[0]["recommendation"]
    assert plan[0]["requires_manual_review"] is True