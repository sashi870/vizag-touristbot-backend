import json
import httpx

payload = {
    "query": "ఎంవీపీ దగ్గర ఆసుపత్రులు",
    "original_query": "ఎంవీపీ దగ్గర ఆసుపత్రులు",
    "language": "Telugu",
    "session_id": "async-telugu-python-test-123456789",
}

response = httpx.post(
    "http://127.0.0.1:8000/chat",
    json=payload,
    timeout=30.0,
)

print("Status:", response.status_code)
print(json.dumps(response.json(), ensure_ascii=False, indent=2))