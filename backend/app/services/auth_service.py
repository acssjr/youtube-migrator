import json
from pathlib import Path
from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from loguru import logger
from app.config.config import settings

# YouTube scopes required: read to view, write to upload
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

class AuthService:
    @staticmethod
    def get_flow() -> Flow:
        """Create a Google OAuth Flow instance."""
        secrets_file = settings.base_dir / settings.GOOGLE_CLIENT_SECRETS_FILE
        
        # Check if client_secret.json exists
        if secrets_file.exists():
            return Flow.from_client_secrets_file(
                str(secrets_file),
                scopes=SCOPES,
                redirect_uri=settings.GOOGLE_REDIRECT_URI
            )
            
        # Fallback to config settings if no file
        if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
            client_config = {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
                }
            }
            return Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=settings.GOOGLE_REDIRECT_URI
            )
            
        raise ValueError("Google OAuth credentials are not configured. Please supply client_secret.json.")

    def get_auth_url(self, account_name: str) -> str:
        """Generate Authorization URL for YouTube account oauth."""
        try:
            flow = self.get_flow()
            # Generate authorization URL (this sets flow.code_verifier internally)
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent"
            )
            
            # Serialize account name AND PKCE code_verifier into state
            state_data = {
                "account_name": account_name,
                "code_verifier": getattr(flow, "code_verifier", None)
            }
            
            # Override state in the generated authorization URL
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed_url = urlparse(authorization_url)
            query = parse_qs(parsed_url.query)
            query['state'] = [json.dumps(state_data)]
            new_query = urlencode(query, doseq=True)
            authorization_url = urlunparse(parsed_url._replace(query=new_query))
            
            return authorization_url
        except Exception as e:
            logger.error(f"Error generating OAuth URL: {e}")
            return f"http://localhost:8000/api/auth/error?reason=no_credentials"

    def get_credentials_from_code(self, code: str, state_json: str) -> Dict[str, Any]:
        """Exchange auth code for user credentials and get channel details."""
        try:
            state_data = json.loads(state_json)
            account_name = state_data.get("account_name", "YouTube Account")
            code_verifier = state_data.get("code_verifier")
        except Exception:
            account_name = "YouTube Account"
            code_verifier = None

        flow = self.get_flow()
        flow.fetch_token(code=code, code_verifier=code_verifier)
        credentials = flow.credentials
        
        # Build credentials dictionary to save to database
        credentials_dict = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

        # Query YouTube API for channel info
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
        
        if not response.get("items"):
            raise ValueError("No YouTube channel found for this account.")
            
        channel = response["items"][0]
        channel_id = channel["id"]
        channel_title = channel["snippet"]["title"]

        return {
            "account_name": account_name,
            "channel_id": channel_id,
            "channel_title": channel_title,
            "token_data": credentials_dict
        }

    @staticmethod
    def get_user_credentials(token_data: Dict[str, Any]) -> Credentials:
        """Reconstruct Credentials object from stored DB dictionary."""
        return Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )
