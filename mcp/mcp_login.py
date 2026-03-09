import os
import json
import urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from splitwise import Splitwise

# Load credentials from .env
ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)

CACHE_FILE = Path(__file__).parent / "mcp_cache.json"

PORT = 5005
REDIRECT_URI = f"http://127.0.0.1:{PORT}/mcp_callback"

def get_keys():
    key = os.getenv("CONSUMER_KEY")
    secret = os.getenv("CONSUMER_SECRET")
    if not key or not secret:
        print("Error: CONSUMER_KEY or CONSUMER_SECRET missing from .env")
        exit(1)
    return key, secret

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == "/mcp_callback":
            query_components = urllib.parse.parse_qs(parsed_path.query)
            
            if 'code' not in query_components:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Authorization code not found in request.")
                return

            code = query_components['code'][0]
            
            # Trade code for access token
            key, secret = get_keys()
            client = Splitwise(consumer_key=key, consumer_secret=secret)
            try:
                token_dict = client.getOAuth2AccessToken(code, REDIRECT_URI)
                access_token = token_dict.get("access_token")
                
                if access_token:
                    # Save token to mcp_cache.json
                    with open(CACHE_FILE, "w") as f:
                        json.dump({"access_token": access_token}, f)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body><h2>Success!</h2><p>Your Splitwise account is now securely linked to the MCP Server.</p><p>You can close this tab and return to the terminal.</p></body></html>")
                    print(f"\n✅ Successfully authenticated and saved token to {CACHE_FILE.name}")
                    
                    # Stop the server
                    # We run this in a thread or just let the handle_request loop finish
                    self.server.done = True
                else:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"Failed to obtain access token.")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error during token exchange: {str(e)}".encode())
                print(f"Error exchange: {e}")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found.")

    def log_message(self, format, *args):
        # Suppress HTTP logging for cleaner terminal output
        pass

def main():
    print("\n--- Splitwise MCP Auth Setup ---")
    key, secret = get_keys()
    
    # Generate authorization URL
    client = Splitwise(consumer_key=key, consumer_secret=secret)
    url, state = client.getOAuth2AuthorizeURL(REDIRECT_URI)
    
    print("\n1. Please visit the following URL to authorize the MCP Server:")
    print(f"\n   {url}\n")
    print("2. Waiting for callback...")
    
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    httpd.done = False
    
    while not httpd.done:
        httpd.handle_request()
        
    print("Auth complete. You can now start the MCP server.")

if __name__ == "__main__":
    main()
