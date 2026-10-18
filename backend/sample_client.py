
import requests

response = requests.get("https://api.example.com/users/123")
result = requests.post(
    "https://api.example.com/users",
    json={"name": "Test User"},
)
