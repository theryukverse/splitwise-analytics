import os
import sys

from util import get_splitwise_client
try:
    client = get_splitwise_client()
    friends = client.getFriends()
    print("Success! Found", len(friends), "friends.")
except Exception as e:
    print("Exception:", type(e).__name__, str(e))
