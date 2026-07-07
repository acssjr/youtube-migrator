from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database.db import get_session
from app.repositories.settings_repository import SettingsRepository
from app.schemas.schemas import SettingsUpdateRequest, SettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=SettingsResponse)
def get_settings(session: Session = Depends(get_session)):
    """Retrieve all saved app settings."""
    settings_repo = SettingsRepository(session)
    saved_settings = settings_repo.get_all()
    
    # Fill in defaults if not set in database
    defaults = {
        "default_account_id": saved_settings.get("default_account_id", ""),
        "default_channel_id": saved_settings.get("default_channel_id", ""),
        "temp_downloads_dir": saved_settings.get("temp_downloads_dir", "downloads"),
        "theme": saved_settings.get("theme", "dark")
    }
    return SettingsResponse(settings=defaults)

@router.post("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    session: Session = Depends(get_session)
):
    """Save app settings to the database."""
    settings_repo = SettingsRepository(session)
    
    if payload.default_account_id is not None:
        settings_repo.set_value("default_account_id", payload.default_account_id)
    if payload.default_channel_id is not None:
        settings_repo.set_value("default_channel_id", payload.default_channel_id)
    if payload.temp_downloads_dir is not None:
        settings_repo.set_value("temp_downloads_dir", payload.temp_downloads_dir)
    if payload.theme is not None:
        settings_repo.set_value("theme", payload.theme)
        
    saved_settings = settings_repo.get_all()
    return SettingsResponse(settings=saved_settings)
