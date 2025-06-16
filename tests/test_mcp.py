import requests

url = "http://localhost:8000/api/mcp.json/"
payload = {
    "jsonrpc": "2.0",
    "method": "file_system_create_directory",
    "params": {"path": "tmp/newdir"},
    "id": 1
}
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"  # <---- BOTH!
}

resp = requests.post(url, json=payload, headers=headers)
print("Status:", resp.status_code)
print("Response:", repr(resp.text))
print("Headers:", resp.headers)
