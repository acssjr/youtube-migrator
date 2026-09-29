import unittest
from datetime import datetime

from fastapi import HTTPException, Response
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from starlette.requests import Request

from app.api.auth import get_accounts, delete_account
from app.config.config import settings
from app.models.models import CloudOAuthAccount
from app.services.cloud_session import COOKIE_NAME, new_owner_id


class CloudAccountsTests(unittest.TestCase):
    def setUp(self):
        self.original_vercel = settings.VERCEL
        settings.VERCEL = "1"
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.owner = new_owner_id()
        self.other_owner = new_owner_id()
        with Session(self.engine) as session:
            for owner, channel in [(self.owner, "a"), (self.owner, "b"), (self.other_owner, "c")]:
                session.add(CloudOAuthAccount(owner_id=owner, channel_id=channel,
                                              account_name=channel, channel_title=channel,
                                              encrypted_token="encrypted", created_at=datetime.utcnow()))
            session.commit()

    def tearDown(self):
        settings.VERCEL = self.original_vercel
        self.engine.dispose()

    def test_accounts_are_persistent_and_scoped_to_browser(self):
        def request(owner):
            return Request({"type": "http", "headers": [(b"cookie", f"{COOKIE_NAME}={owner}".encode())]})

        with Session(self.engine) as session:
            accounts = get_accounts(request(self.owner), Response(), session)
            self.assertEqual({account.channel_id for account in accounts}, {"a", "b"})
            account_id = accounts[0].id
            with self.assertRaises(HTTPException) as rejected:
                delete_account(account_id, request(self.other_owner), session)
            self.assertEqual(rejected.exception.status_code, 404)
            self.assertEqual([account.channel_id for account in get_accounts(request(self.other_owner), Response(), session)], ["c"])
            delete_account(account_id, request(self.owner), session)
            self.assertEqual(len(get_accounts(request(self.owner), Response(), session)), 1)


if __name__ == "__main__":
    unittest.main()
