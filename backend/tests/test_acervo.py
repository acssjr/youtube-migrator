import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.db import get_session


class AcervoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_session] = session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.engine.dispose()

    def test_owner_isolation_exact_text_and_versions(self):
        with patch('app.api.acervo.acervo_owner', return_value='one'):
            record = self.client.post('/api/acervo/records', json={'kind':'approved_text','payload':{'text':'Sobre o compositor:\n  Texto EXATO.\n'}}).json()
            self.assertEqual(record['payload']['text'], 'Sobre o compositor:\n  Texto EXATO.\n')
            self.assertEqual(self.client.patch('/api/acervo/records/'+record['id'], json={'payload':{'text':'Novo texto'}}).status_code, 200)
            versions = self.client.get('/api/acervo/records/'+record['id']+'/versions').json()
            self.assertEqual(versions[0]['payload']['text'], 'Sobre o compositor:\n  Texto EXATO.\n')
        with patch('app.api.acervo.acervo_owner', return_value='two'):
            self.assertEqual(self.client.get('/api/acervo/records').json(), [])
            self.assertEqual(self.client.patch('/api/acervo/records/'+record['id'],json={'payload':{}}).status_code,404)
            self.assertEqual(self.client.get('/api/acervo/records/'+record['id']+'/versions').json(),[])

    def test_update_conflict_and_unknown_kind(self):
        with patch('app.api.acervo.acervo_owner', return_value='one'):
            self.assertEqual(self.client.post('/api/acervo/records',json={'kind':'token','payload':{}}).status_code,422)
            record=self.client.post('/api/acervo/records',json={'kind':'work','payload':{'name':'Allah'}}).json()
            self.assertEqual(self.client.patch('/api/acervo/records/'+record['id'], json={'payload':{},'expected_updated_at':'old'}).status_code,409)
