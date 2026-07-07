from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session
from typing import List

from app.database.db import get_session
from app.models.models import OAuthToken
from app.repositories.token_repository import TokenRepository
from app.schemas.schemas import AuthURLResponse, AccountResponse, CallbackRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()

@router.get("/url", response_model=AuthURLResponse)
def get_auth_url(account_name: str = Query(..., description="Name for this YouTube account profile")):
    """Get Google OAuth URL to authenticate a YouTube channel."""
    url = auth_service.get_auth_url(account_name)
    return AuthURLResponse(url=url)

@router.get("/callback")
def oauth_callback(
    code: str,
    state: str,
    session: Session = Depends(get_session)
):
    """Handle OAuth redirect from Google, retrieve credentials and save to database."""
    try:
        token_data = auth_service.get_credentials_from_code(code, state)
        
        token_repo = TokenRepository(session)
        # Check if this channel token is already authenticated
        existing = token_repo.get_by_channel_id(token_data["channel_id"])
        
        if existing:
            # Update credentials
            existing.account_name = token_data["account_name"]
            existing.token_data = token_data["token_data"]
            existing.channel_title = token_data["channel_title"]
            token_repo.save(existing)
        else:
            # Create new token record
            new_token = OAuthToken(
                account_name=token_data["account_name"],
                channel_id=token_data["channel_id"],
                channel_title=token_data["channel_title"],
                token_data=token_data["token_data"]
            )
            token_repo.save(new_token)
            
        # Redirect back to frontend settings page to show connection success
        return RedirectResponse(url="http://localhost:5173/settings?auth=success")
    except Exception as e:
        # Redirect with error status
        return RedirectResponse(url=f"http://localhost:5173/settings?auth=error&reason={str(e)}")

@router.get("/accounts", response_model=List[AccountResponse])
def get_accounts(session: Session = Depends(get_session)):
    """List all connected YouTube accounts/channels."""
    token_repo = TokenRepository(session)
    accounts = token_repo.get_all()
    return [
        AccountResponse(
            id=acc.id,
            account_name=acc.account_name,
            channel_id=acc.channel_id,
            channel_title=acc.channel_title,
            created_at=acc.created_at
        ) for acc in accounts
    ]

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, session: Session = Depends(get_session)):
    """Remove a connected YouTube account token."""
    token_repo = TokenRepository(session)
    success = token_repo.delete(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"message": "Account deleted successfully."}
