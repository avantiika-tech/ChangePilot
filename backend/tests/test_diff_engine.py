import re
from urllib.parse import urlparse
from app.diff_engine import compare_specs
from app.impact_analyzer import analyze_python_file, match_changes_to_calls


def test_detects_added_required_parameter():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "include",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "added_parameter"
        and change["evidence"]["parameter"] == "include"
        and change["breaking"] is True
        for change in changes
    )


def test_detects_parameter_type_change():
    old_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ]
                }
            }
        }
    }

    new_spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ]
                }
            }
        }
    }

    changes = compare_specs(old_spec, new_spec)

    assert any(
        change["type"] == "parameter_type_changed"
        and change["evidence"]["old_type"] == "integer"
        and change["evidence"]["new_type"] == "string"
        for change in changes
    )



def test_analyzer_detects_http_calls(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'requests.get("https://api.example.com/users/123")\n'
        'requests.post("https://api.example.com/users")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 2
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users/123"
    assert findings[1]["method"] == "POST"


def test_matches_api_change_to_affected_call():
    changes = [
        {
            "type": "parameter_type_changed",
            "method": "GET",
            "path": "/users/{id}",
            "breaking": True,
        }
    ]

    findings = [
        {
            "file": "client.py",
            "line": 2,
            "method": "GET",
            "url": "https://api.example.com/users/123",
            "call": "requests.get",
        },
        {
            "file": "client.py",
            "line": 3,
            "method": "POST",
            "url": "https://api.example.com/users",
            "call": "requests.post",
        },
    ]

    results = match_changes_to_calls(changes, findings)

    assert results[0]["potential_impact_count"] == 1
    assert results[0]["affected_calls"][0]["call"] == "requests.get"



def test_detects_missing_required_query_parameter():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "old_parameter": None,
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 10,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123",
    }

    from app.impact_analyzer import match_changes_to_calls

    impacts = match_changes_to_calls([change], [finding])

    assert len(impacts) == 1
    assert impacts[0]["potential_impact_count"] == 1

    affected_call = impacts[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "include"
    assert affected_call["parameter_status"] == "missing_from_literal_url"



def test_detects_present_required_query_parameter():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 12,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123?include=orders",
    }

    from app.impact_analyzer import match_changes_to_calls

    impacts = match_changes_to_calls([change], [finding])

    affected_call = impacts[0]["affected_calls"][0]
    assert affected_call["required_parameter"] == "include"
    assert affected_call["parameter_status"] == "present"



def test_end_to_end_spec_diff_and_python_impact(tmp_path):
    from pathlib import Path
    from app.diff_engine import load_spec, compare_specs
    from app.impact_analyzer import (
        analyze_python_project,
        match_changes_to_calls,
    )

    project_root = Path(__file__).resolve().parents[1]

    old_spec = load_spec(project_root / "samples" / "v1.yaml")
    new_spec = load_spec(project_root / "samples" / "v2.yaml")

    changes = compare_specs(old_spec, new_spec)

    client_file = tmp_path / "client.py"
    client_file.write_text(
        'import requests\n'
        'requests.get("https://api.example.com/users/123")\n',
        encoding="utf-8",
    )

    findings = analyze_python_project(tmp_path)
    impacts = match_changes_to_calls(changes, findings)

    assert len(findings) == 1
    assert len(impacts) == len(changes)

    include_impacts = [
        impact
        for impact in impacts
        if impact["change"].get("type") == "added_parameter"
        and impact["change"].get("evidence", {}).get("parameter") == "include"
    ]

    assert len(include_impacts) == 1

    affected_call = include_impacts[0]["affected_calls"][0]
    assert affected_call["parameter_status"] == "missing_from_literal_url"
    assert affected_call["required_parameter"] == "include"



def test_analyzer_resolves_url_constant(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'BASE_URL = "https://api.example.com"\n'
        'requests.get(BASE_URL + "/users/123")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] == "https://api.example.com/users/123"


def test_detects_required_query_parameter_in_params_dict():
    change = {
        "type": "added_parameter",
        "method": "GET",
        "path": "/users/{id}",
        "evidence": {
            "parameter": "include",
            "in": "query",
            "new_required": True,
        },
    }

    finding = {
        "file": "client.py",
        "line": 5,
        "call": "requests.get",
        "method": "GET",
        "url": "https://api.example.com/users/123",
        "params": {"include": "orders"},
    }

    impacts = match_changes_to_calls([change], [finding])
    affected_call = impacts[0]["affected_calls"][0]

    assert affected_call["parameter_status"] == "present"


def test_dynamic_url_is_not_reported_as_literal_url(tmp_path):
    sample_file = tmp_path / "client.py"
    sample_file.write_text(
        'import requests\n'
        'user_id = get_user_id()\n'
        'requests.get(f"https://api.example.com/users/{user_id}")\n',
        encoding="utf-8",
    )

    findings = analyze_python_file(sample_file)

    assert len(findings) == 1
    assert findings[0]["method"] == "GET"
    assert findings[0]["url"] is None
