import secrets
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from app.api import download_controls, downloads
from app.database.db import get_session
from app.models.models import DownloadJob
from app.models.download_control_models import DownloadJobControl
from app.services.download_jobs import DownloadQueue
from app.config.config import settings


class QueueControlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.owner, self.other = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.queue = DownloadQueue()
        self.app = FastAPI()
        self.app.include_router(download_controls.router, prefix='/api')
        def session():
            with Session(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_session] = session
        self.client = TestClient(self.app)
        self.client.cookies.set(downloads.COOKIE, self.owner)
        self.remote = patch('app.api.download_controls.use_remote', return_value=False)
        self.remote.start()
        self.ids = ['a' * 32, 'b' * 32, 'c' * 32]
        with Session(self.engine) as db:
            for index, identifier in enumerate(self.ids):
                db.add(DownloadJob(id=identifier, owner_id=self.owner if index < 2 else self.other,
                    video_id='BaW_jenozKc', format='mp3',
                    created_at=datetime.utcnow() + timedelta(seconds=index), expires_at=datetime.utcnow() + timedelta(days=1)))
            db.commit()

    def tearDown(self):
        self.remote.stop()
        self.client.close()
        self.engine.dispose()

    def test_pause_is_persistent_and_scoped_to_owner(self):
        self.assertEqual(self.client.post('/api/download-controls/pause', json={'paused': True}).status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(self.queue.next_job(db).id, self.ids[2])
        self.assertTrue(self.client.get('/api/download-controls').json()['paused'])
        self.client.post('/api/download-controls/pause', json={'paused': False})
        with Session(self.engine) as db:
            self.assertEqual(self.queue.next_job(db).id, self.ids[0])

    def test_reorder_rejects_cross_owner_and_stale_or_duplicate_lists(self):
        for ids in [self.ids, [self.ids[0]], [self.ids[0], self.ids[0]]]:
            self.assertEqual(self.client.post('/api/download-controls/reorder', json={'job_ids': ids}).status_code, 409)
        ids = self.ids[:2][::-1]
        self.assertEqual(self.client.post('/api/download-controls/reorder', json={'job_ids': ids}).json()['job_ids'], ids)
        with Session(self.engine) as db:
            self.assertEqual(self.queue.next_job(db).id, ids[0])

    def test_cancel_is_idempotent_and_rejects_other_owners(self):
        self.assertEqual(self.client.post(f'/api/download-controls/jobs/{self.ids[2]}/cancel').status_code, 404)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/download-controls/jobs/{self.ids[0]}/cancel').status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.get(DownloadJob, self.ids[0]).status, 'cancelled')
            self.assertEqual(self.queue.next_job(db).id, self.ids[1])

    def test_cancelling_running_download_terminates_real_subprocess(self):
        old_directory = settings.DOWNLOADS_DIR
        with tempfile.TemporaryDirectory() as directory:
            settings.DOWNLOADS_DIR = directory
            actual_popen = subprocess.Popen
            processes = []
            def launch(*args, **kwargs):
                if args and args[0][0] == 'taskkill':
                    return actual_popen(*args, **kwargs)
                process = actual_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
                processes.append(process)
                return process
            def cancel_on_wait(_timeout):
                with Session(self.engine) as db:
                    download_controls.cancel_job(db, self.owner, self.ids[0])
                return False
            try:
                with Session(self.engine) as db, patch('app.services.download_jobs.subprocess.Popen', side_effect=launch), \
                        patch.object(self.queue.stop_event, 'wait', side_effect=cancel_on_wait), \
                        patch('app.services.download_jobs.download_engine.snapshot', return_value=(sys.executable, 'test')):
                    self.queue.execute(db, db.get(DownloadJob, self.ids[0]))
                self.assertIsNotNone(processes[0].poll())
                with Session(self.engine) as db:
                    self.assertEqual(db.get(DownloadJob, self.ids[0]).status, 'cancelled')
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                settings.DOWNLOADS_DIR = old_directory


if __name__ == '__main__':
    unittest.main()
