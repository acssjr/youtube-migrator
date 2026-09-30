from datetime import datetime, timedelta
import io
import secrets
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.api import download_packages, downloads
from app.config.config import settings
from app.database.db import get_session
from app.models.models import DownloadJob
from app.services.download_jobs import job_directory


class DownloadPackagesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.saved = settings.DOWNLOADS_DIR
        settings.DOWNLOADS_DIR = self.directory.name
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.owner = secrets.token_urlsafe(32)
        app = FastAPI()
        app.include_router(download_packages.router, prefix='/api')
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_session] = session
        self.client = TestClient(app)
        self.client.cookies.set(downloads.COOKIE, self.owner)
        self.local = patch.object(download_packages, 'use_remote', return_value=False)
        self.local.start()

    def tearDown(self):
        self.local.stop()
        self.client.close()
        settings.DOWNLOADS_DIR = self.saved
        self.engine.dispose()
        self.directory.cleanup()

    def job(self, number, *, status='completed', owner=None, title='Marcha / Teste', expired=False):
        identifier = f'{number:032x}'
        with Session(self.engine) as db:
            db.add(DownloadJob(id=identifier, owner_id=owner or self.owner, video_id=f'{number:011d}',
                format='mp3', title=title, status=status, message='Falhou a conversão' if status == 'error' else '',
                expires_at=datetime.utcnow() + timedelta(hours=-1 if expired else 24)))
            db.commit()
        if status == 'completed':
            root = job_directory(identifier)
            root.mkdir(parents=True)
            (root / 'media.mp3').write_bytes(f'audio {number}'.encode())
        return identifier

    def create(self, identifiers):
        return self.client.post('/api/download-packages', json={'job_ids': identifiers, 'title': 'Retreta'})

    def test_package_preserves_order_and_reports_failures_without_media_download(self):
        first = self.job(1)
        second = self.job(2, title='Segunda música')
        failed = self.job(3, status='error')
        result = self.create([second, failed, first])
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['included'], 2)
        self.assertEqual(result.json()['missing'], 1)
        archive_response = self.client.get(result.json()['url'])
        self.assertEqual(archive_response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
            names = archive.namelist()
            self.assertEqual(names[:2], ['01 — Segunda música.mp3', '03 — Marcha _ Teste.mp3'])
            self.assertEqual(archive.read(names[0]), b'audio 2')
            self.assertIn('Falhou a conversão', archive.read('relatorio.txt').decode())
            self.assertIn('Segunda música', archive.read('lista-de-faixas.csv').decode('utf-8-sig'))
        self.assertEqual(self.client.get(result.json()['url']).status_code, 404)

    def test_all_items_checked_before_packaging_and_foreign_owner_cannot_read(self):
        own = self.job(1)
        foreign = self.job(2, owner=secrets.token_urlsafe(32))
        self.assertEqual(self.create([own, foreign]).status_code, 404)
        self.assertFalse(download_packages.packages_directory().exists())
        result = self.create([own])
        self.client.cookies.set(downloads.COOKIE, secrets.token_urlsafe(32))
        self.assertEqual(self.client.get(result.json()['url']).status_code, 404)

    def test_expired_and_missing_files_remain_in_report(self):
        expired = self.job(1, expired=True)
        missing = self.job(2)
        (job_directory(missing) / 'media.mp3').unlink()
        result = self.create([expired, missing])
        self.assertEqual(result.json()['included'], 0)
        self.assertEqual(result.json()['missing'], 2)
        with zipfile.ZipFile(io.BytesIO(self.client.get(result.json()['url']).content)) as archive:
            self.assertEqual(archive.namelist(), ['lista-de-faixas.csv', 'relatorio.txt'])

    def test_duplicate_or_traversal_ids_and_remote_are_rejected(self):
        own = self.job(1)
        self.assertEqual(self.create([own, own]).status_code, 422)
        self.assertEqual(self.create(['../secret']).status_code, 422)
        with patch.object(download_packages, 'use_remote', return_value=True), patch.object(download_packages, 'remote', return_value={'url': 'https://worker.example/file', 'included': 1}) as upstream:
            self.assertEqual(self.create([own]).json()['included'], 1)
            self.assertEqual(upstream.call_args.kwargs['json']['owner_id'], self.owner)


if __name__ == '__main__':
    unittest.main()
