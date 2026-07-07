from typing import Dict, Optional
from sqlmodel import Session, select
from app.models.models import AppSetting

class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self) -> Dict[str, str]:
        statement = select(AppSetting)
        settings = self.session.exec(statement).all()
        return {s.key: s.value for s in settings}

    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        setting = self.session.get(AppSetting, key)
        return setting.value if setting else default

    def set_value(self, key: str, value: str) -> AppSetting:
        setting = self.session.get(AppSetting, key)
        if setting:
            setting.value = value
        else:
            setting = AppSetting(key=key, value=value)
        self.session.add(setting)
        self.session.commit()
        self.session.refresh(setting)
        return setting
