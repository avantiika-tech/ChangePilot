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
