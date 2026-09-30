from datetime import datetime, timedelta
import secrets
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mutagen.mp3 import MP3
from mutagen.id3 import COMM
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.api import mp3_tags, downloads
from app.config.config import settings
from app.database.db import get_session
from app.models.models import DownloadJob
from app.services.download_jobs import job_directory


class Mp3TagsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_dir = settings.DOWNLOADS_DIR
        settings.DOWNLOADS_DIR = self.temp.name
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.owner = secrets.token_urlsafe(32)
        app = FastAPI()
        app.include_router(mp3_tags.router, prefix='/api')
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_session] = session
        self.client = TestClient(app)
        self.client.cookies.set(downloads.COOKIE, self.owner)
        self.local = patch.object(mp3_tags, 'use_remote', return_value=False)
        self.local.start()

    def tearDown(self):
        self.local.stop()
        self.client.close()
        self.engine.dispose()
        settings.DOWNLOADS_DIR = self.original_dir
        self.temp.cleanup()

    def job(self, number, owner=None, expired=False):
        identifier = f'{number:032x}'
        with Session(self.engine) as db:
            db.add(DownloadJob(id=identifier, owner_id=owner or self.owner, video_id='00000000001', format='mp3', status='completed', expires_at=datetime.utcnow() + timedelta(hours=-1 if expired else 24)))
            db.commit()
        directory = job_directory(identifier)
        directory.mkdir(parents=True)
        (directory / 'media.mp3').write_bytes((bytes.fromhex('fffb9064') + bytes(413)) * 10)
        return identifier

    def apply(self, ids, tags):
        return self.client.post('/api/mp3-tags', json={'job_ids': ids, 'tags': tags})

    def test_preserves_exact_names_and_unselected_tags(self):
        identifier = self.job(1)
        self.assertTrue(self.apply([identifier], {'artist': 'Sociedade Filarmônica União Sanfelixta', 'composer': 'Estevam Moura', 'title': 'Allah', 'notes': 'Texto exato\nsegunda linha'}).json()['results'][0]['applied'])
        self.apply([identifier], {'album': 'Retreta — 5ª Noite', 'track': '1/8', 'year': '2026'})
        tags = self.client.get('/api/mp3-tags/' + identifier).json()['tags']
        self.assertEqual(tags['artist'], 'Sociedade Filarmônica União Sanfelixta')
        self.assertEqual(tags['composer'], 'Estevam Moura')
        self.assertEqual(tags['notes'], 'Texto exato\nsegunda linha')
        self.assertEqual(tags['track'], '1/8')
        self.apply([identifier], {'title': ''})
        self.assertEqual(self.client.get('/api/mp3-tags/' + identifier).json()['tags']['title'], '')

    def test_foreign_file_blocks_entire_batch_and_expired_file_rejected(self):
        own = self.job(1)
        foreign = self.job(2, owner=secrets.token_urlsafe(32))
        self.assertEqual(self.apply([own, foreign], {'composer': 'Nome'}).status_code, 404)
        self.assertEqual(self.client.get('/api/mp3-tags/' + own).json()['tags']['composer'], '')
        self.assertEqual(self.client.get('/api/mp3-tags/' + foreign).status_code, 404)
        self.assertEqual(self.apply([self.job(3, expired=True)], {'composer': 'Nome'}).status_code, 410)

    def test_invalid_and_unreadable_files_leave_original_bytes(self):
        identifier = self.job(1)
        path = job_directory(identifier) / 'media.mp3'
        path.write_bytes(b'not an mp3')
        self.assertFalse(self.apply([identifier], {'title': 'Teste'}).json()['results'][0]['applied'])
        self.assertEqual(path.read_bytes(), b'not an mp3')
        self.assertEqual(list(path.parent.glob('tags-*')), [])
        self.assertEqual(self.apply([identifier], {'year': 'hoje'}).status_code, 422)
        self.assertEqual(self.apply(['../secret'], {'title': 'x'}).status_code, 422)

    def test_remote_owner_is_forwarded_only_to_worker(self):
        identifier = self.job(1)
        with patch.object(mp3_tags, 'use_remote', return_value=True), patch.object(mp3_tags, 'remote', return_value={'results': []}) as upstream:
            self.apply([identifier], {'composer': 'Nome'})
            self.assertEqual(upstream.call_args.kwargs['json']['owner_id'], self.owner)


if __name__ == '__main__':
    unittest.main()
