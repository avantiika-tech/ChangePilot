
from app.impact_analyzer import analyze_python_file


def test_detects_requests_get_call(tmp_path):
    source_file = tmp_path / "client.py"
    source_file.write_text(
        'import requests\n'
        'response = requests.get("https://api.example.com/users")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(source_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users"
    assert findings[0]["call"] == "requests.get"



def test_resolves_url_constant(tmp_path):
    source_file = tmp_path / "client.py"
    source_file.write_text(
        'import requests\n'
        'BASE_URL = "https://api.example.com"\n'
        'ENDPOINT = BASE_URL + "/users"\n'
        'response = requests.get(ENDPOINT)\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(source_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users"


def test_records_dynamic_url_as_unresolved(tmp_path):
    source_file = tmp_path / "client.py"
    source_file.write_text(
        'import requests\n'
        'user_id = get_user_id()\n'
        'url = f"https://api.example.com/users/{user_id}"\n'
        'response = requests.get(url)\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(source_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] is None



def test_extracts_static_query_params(tmp_path):
    source_file = tmp_path / "client.py"
    source_file.write_text(
        'import requests\n'
        'response = requests.get(\n'
        '    "https://api.example.com/users",\n'
        '    params={"page": 2, "limit": 10}\n'
        ')\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(source_file)

    assert len(findings) == 1
    assert findings[0]["params"] == {"page": 2, "limit": 10}


def test_matches_api_change_to_python_call():
    from app.impact_analyzer import match_changes_to_calls

    changes = [
        {
            "type": "removed_endpoint",
            "severity": "high",
            "breaking": True,
            "method": "GET",
            "path": "/users",
            "message": "GET /users was removed.",
            "evidence": {},
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 5,
            "method": "GET",
            "url": "https://api.example.com/users",
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls(changes, findings)

    assert len(results) == 1
    assert results[0]["potential_impact_count"] == 1
    assert results[0]["affected_calls"][0]["call"] == "requests.get"



def test_matches_path_parameter_endpoint():
    from app.impact_analyzer import match_changes_to_calls

    changes = [
        {
            "type": "parameter_type_changed",
            "severity": "high",
            "method": "GET",
            "path": "/users/{user_id}",
            "message": "The user_id parameter type changed.",
            "evidence": {
                "in": "path",
                "parameter": "user_id",
                "old_type": "string",
                "new_type": "integer",
            },
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 10,
            "method": "GET",
            "url": "https://api.example.com/users/123",
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls(changes, findings)

    assert len(results) == 1
    assert results[0]["potential_impact_count"] == 1

    affected_call = results[0]["affected_calls"][0]
    assert affected_call["url"] == "https://api.example.com/users/123"
    assert affected_call["parameter_evidence"]["parameter"] == "user_id"
    assert affected_call["match_evidence"]["matched_request_path"] == "/users/123"



def test_does_not_match_different_http_method():
    from app.impact_analyzer import match_changes_to_calls

    changes = [
        {
            "type": "removed_endpoint",
            "severity": "high",
            "method": "GET",
            "path": "/users/{user_id}",
            "message": "GET endpoint removed.",
            "evidence": {},
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 15,
            "method": "POST",
            "url": "https://api.example.com/users/123",
            "call": "requests.post",
        }
    ]

    results = match_changes_to_calls(changes, findings)

    assert len(results) == 1
    assert results[0]["potential_impact_count"] == 0
    assert results[0]["affected_calls"] == []



def test_detects_required_query_parameter_in_url():
    from app.impact_analyzer import match_changes_to_calls

    changes = [
        {
            "type": "added_parameter",
            "severity": "high",
            "method": "GET",
            "path": "/users",
            "message": "Required query parameter 'page' added.",
            "evidence": {
                "in": "query",
                "parameter": "page",
                "required": True,
            },
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 12,
            "method": "GET",
            "url": "https://api.example.com/users?page=2",
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls(changes, findings)

    assert results[0]["potential_impact_count"] == 1

    affected_call = results[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "page"
    assert affected_call["parameter_status"] == "present"
    assert affected_call["parameter_source"] == "url_query"



def test_flags_missing_required_query_parameter():
    from app.impact_analyzer import match_changes_to_calls

    changes = [
        {
            "type": "added_parameter",
            "severity": "high",
            "method": "GET",
            "path": "/users",
            "message": "Required query parameter 'page' added.",
            "evidence": {
                "in": "query",
                "parameter": "page",
                "required": True,
            },
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 12,
            "method": "GET",
            "url": "https://api.example.com/users",
            "call": "requests.get",
        }
    ]

    results = match_changes_to_calls(changes, findings)

    assert results[0]["potential_impact_count"] == 1

    affected_call = results[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "page"
    assert affected_call["parameter_status"] == "missing_from_literal_url"
    assert affected_call["parameter_source"] is None
