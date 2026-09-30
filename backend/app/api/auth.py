from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from typing import List

from app.database.db import get_session
from app.models.models import OAuthToken, CloudOAuthAccount
from app.repositories.token_repository import TokenRepository
from app.schemas.schemas import AuthURLResponse, AccountResponse, CallbackRequest
from app.services.auth_service import AuthService
from app.config.config import settings
from app.services.cloud_session import COOKIE_NAME, COOKIE_AGE, cloud_mode, encode_session, read_session, new_owner_id, decode_token
from datetime import datetime, timezone
import json
import secrets
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()

@router.get("/error")
def oauth_error():
    """Recover old local authorization URLs in the settings screen."""
    import os
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    target = "/" if cloud_mode() else f"{frontend}/settings"
    query = urlencode({"auth": "error", "reason": "A conexão Google não está configurada. Configure as credenciais OAuth para esta instalação."})
    return RedirectResponse(url=f"{target}?{query}")

@router.get("/url", response_model=AuthURLResponse)
def get_auth_url(account_name: str = Query(..., description="Name for this YouTube account profile")):
    """Get Google OAuth URL to authenticate a YouTube channel."""
    if cloud_mode() and (not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET
                         or settings.GOOGLE_REDIRECT_URI.startswith("http://localhost")):
        raise HTTPException(503, "A integração Google ainda não foi configurada neste deploy.")
    if cloud_mode() and not settings.DATABASE_URL.startswith("postgres"):
        raise HTTPException(503, "O banco de contas ainda não foi configurado neste deploy.")
    try:
        url = auth_service.get_auth_url(account_name)
    except ValueError as error:
        raise HTTPException(503, str(error)) from error
    if cloud_mode():
        nonce = secrets.token_urlsafe(24)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "state" in query:
            state = json.loads(query["state"][0])
            state["nonce"] = nonce
            query["state"] = [json.dumps(state)]
            url = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
        response = JSONResponse({"url": url})
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie("yt_acervo_oauth_nonce", nonce, max_age=600, httponly=True, secure=True, samesite="lax")
        return response
    return AuthURLResponse(url=url)

@router.get("/callback")
def oauth_callback(
    code: str,
    state: str,
    request: Request,
    session: Session = Depends(get_session)
):
    """Handle OAuth redirect from Google, retrieve credentials and save to database."""
    try:
        if cloud_mode():
            nonce = json.loads(state).get("nonce", "")
            expected = request.cookies.get("yt_acervo_oauth_nonce", "")
            if not nonce or not expected or not secrets.compare_digest(nonce, expected):
                raise ValueError("Estado OAuth inválido. Inicie a conexão novamente.")
            token_data = auth_service.get_credentials_from_code(code, state)
            try:
                owner_id = read_session(request)["owner_id"]
            except HTTPException:
                owner_id = new_owner_id()
            existing = session.exec(select(CloudOAuthAccount).where(
                CloudOAuthAccount.owner_id == owner_id,
                CloudOAuthAccount.channel_id == token_data["channel_id"])).first()
            if existing and not token_data["token_data"].get("refresh_token"):
                token_data["token_data"]["refresh_token"] = decode_token(existing.encrypted_token).get("refresh_token")
            account = existing or CloudOAuthAccount(owner_id=owner_id,
                                                       channel_id=token_data["channel_id"],
                                                       encrypted_token="")
            account.account_name = token_data["account_name"]
            account.channel_title = token_data["channel_title"]
            account.encrypted_token = encode_session(token_data["token_data"])
            account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(account)
            session.commit()
            response = RedirectResponse(url="/?auth=success")
            response.delete_cookie("yt_acervo_oauth_nonce")
            response.set_cookie(COOKIE_NAME, owner_id, max_age=COOKIE_AGE,
                                httponly=True, secure=True, samesite="lax")
            return response
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
            
        # Determine frontend redirect base based on environment
        import os
        frontend_url = os.getenv("FRONTEND_URL", "")
        if not frontend_url:
            if "localhost:8000" in settings.GOOGLE_REDIRECT_URI:
                frontend_url = "http://localhost:5173"
            else:
                frontend_url = ""
        
        redirect_base = "/" if cloud_mode() else (f"{frontend_url}/settings" if frontend_url else "/settings")
        return RedirectResponse(url=f"{redirect_base}?auth=success")
    except Exception as e:
        import os
        frontend_url = os.getenv("FRONTEND_URL", "")
        if not frontend_url:
            if "localhost:8000" in settings.GOOGLE_REDIRECT_URI:
                frontend_url = "http://localhost:5173"
            else:
                frontend_url = ""
        
        redirect_base = "/" if cloud_mode() else (f"{frontend_url}/settings" if frontend_url else "/settings")
        return RedirectResponse(url=f"{redirect_base}?auth=error&reason={str(e)}")

@router.get("/accounts", response_model=List[AccountResponse])
def get_accounts(request: Request, response: Response, session: Session = Depends(get_session)):
    """List all connected YouTube accounts/channels."""
    response.headers["Cache-Control"] = "no-store"
    if cloud_mode():
        try:
            owner_id = read_session(request)["owner_id"]
        except HTTPException:
            return []
        accounts = session.exec(select(CloudOAuthAccount).where(CloudOAuthAccount.owner_id == owner_id)).all()
        return [AccountResponse(id=account.id, account_name=account.account_name,
                                channel_id=account.channel_id, channel_title=account.channel_title,
                                created_at=account.created_at) for account in accounts]
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
def delete_account(account_id: int, request: Request, session: Session = Depends(get_session)):
    """Remove a connected YouTube account token."""
    if cloud_mode():
        owner_id = read_session(request)["owner_id"]
        account = session.exec(select(CloudOAuthAccount).where(
            CloudOAuthAccount.id == account_id,
            CloudOAuthAccount.owner_id == owner_id)).first()
        if not account:
            raise HTTPException(404, "Canal não encontrado.")
        session.delete(account)
        session.commit()
        response = JSONResponse({"message": "Canal desconectado."})
        response.headers["Cache-Control"] = "no-store"
        return response
    token_repo = TokenRepository(session)
    success = token_repo.delete(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"message": "Account deleted successfully."}
