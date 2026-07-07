from typing import List, Optional
from sqlmodel import Session, select
from app.models.models import OAuthToken

class TokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(self) -> List[OAuthToken]:
        statement = select(OAuthToken)
        return self.session.exec(statement).all()

    def get_by_id(self, token_id: int) -> Optional[OAuthToken]:
        return self.session.get(OAuthToken, token_id)

    def get_by_channel_id(self, channel_id: str) -> Optional[OAuthToken]:
        statement = select(OAuthToken).where(OAuthToken.channel_id == channel_id)
        return self.session.exec(statement).first()

    def save(self, token: OAuthToken) -> OAuthToken:
        self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def delete(self, token_id: int) -> bool:
        token = self.get_by_id(token_id)
        if token:
            self.session.delete(token)
            self.session.commit()
            return True
        return False
