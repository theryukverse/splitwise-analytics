import json
import os
from pathlib import Path
from util import CACHE_FILE, ENV_FILE, get_splitwise_client

print(f"ENV_FILE exists: {ENV_FILE.exists()}")
print(f"CACHE_FILE ({CACHE_FILE}) exists: {CACHE_FILE.exists()}")

if CACHE_FILE.exists():
    with open(CACHE_FILE, "r") as f:
        data = json.load(f)
        print("Cache keys:", data.keys())

try:
    client = get_splitwise_client()
    user = client.getCurrentUser()
    print("Success! Logged in as:", user.getFirstName())
except Exception as e:
    print("Failed to authenticate with Splitwise API:")
    print(type(e).__name__, str(e))
