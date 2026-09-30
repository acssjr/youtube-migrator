import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.config.config import settings
from app.models.models import DownloadJob
from app.models.download_control_models import DownloadJobControl
from app.services.download_jobs import DownloadQueue, job_directory


class DownloadReuseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.directory = tempfile.TemporaryDirectory()
        self.old_directory = settings.DOWNLOADS_DIR
        settings.DOWNLOADS_DIR = self.directory.name
        self.queue = DownloadQueue()
        self.ffmpeg = patch('app.services.download_jobs.shutil.which', return_value='available')
        self.ffmpeg.start()

    def tearDown(self):
        self.ffmpeg.stop()
        settings.DOWNLOADS_DIR = self.old_directory
        self.directory.cleanup()
        self.engine.dispose()

    def seed(self, db, **overrides):
        data = dict(id=uuid.uuid4().hex, owner_id='owner', video_id='BaW_jenozKc', format='mp3',
                    resolution=1080, status='completed', expires_at=datetime.utcnow() + timedelta(hours=1))
        data.update(overrides)
        job = DownloadJob(**data)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def ready(self, job):
        root = job_directory(job.id)
        root.mkdir(parents=True)
        (root / ('media.' + job.format)).write_bytes(b'ready-file')

    def test_completed_reused_without_ffmpeg_or_new_controls(self):
        with Session(self.engine) as db:
            old = self.seed(db)
            self.ready(old)
            with patch('app.services.download_jobs.shutil.which', return_value=None):
                result = self.queue.create(db, 'owner', [old.video_id], 'mp3', 1080)
            self.assertEqual([row.id for row in result], [old.id])
            self.assertEqual(len(db.exec(select(DownloadJob)).all()), 1)
            self.assertEqual(db.exec(select(DownloadJobControl)).all(), [])

    def test_queued_running_and_duplicate_sources_keep_requested_order(self):
        with Session(self.engine) as db:
            first = self.seed(db, status='queued', expires_at=datetime.utcnow() - timedelta(days=1))
            second = self.seed(db, video_id='abcdefghijk', status='running')
            result = self.queue.create(db, 'owner', [second.video_id, first.video_id,
                'https://youtu.be/abcdefghijk', '12345678901'], 'mp3', 1080)
            self.assertEqual([row.video_id for row in result], ['abcdefghijk', 'BaW_jenozKc', '12345678901'])
            self.assertEqual([row.id for row in result[:2]], [second.id, first.id])
            self.assertEqual(len(db.exec(select(DownloadJob)).all()), 3)

    def test_completed_expired_missing_or_empty_file_not_reused(self):
        for condition in ['expired', 'missing', 'empty']:
            with self.subTest(condition=condition), Session(self.engine) as db:
                old = self.seed(db, owner_id=condition)
                if condition != 'missing':
                    self.ready(old)
                if condition == 'expired':
                    old.expires_at = datetime.utcnow() - timedelta(seconds=1)
                    db.add(old)
                    db.commit()
                if condition == 'empty':
                    (job_directory(old.id) / 'media.mp3').write_bytes(b'')
                result = self.queue.create(db, condition, [old.video_id], 'mp3', 1080)
                self.assertNotEqual(result[0].id, old.id)
                self.assertEqual(result[0].status, 'queued')

    def test_owner_format_resolution_and_cancellation_are_respected(self):
        with Session(self.engine) as db:
            others = [self.seed(db, owner_id='other'), self.seed(db, format='mp4'),
                      self.seed(db, resolution=720), self.seed(db, status='error'),
                      self.seed(db, status='cancelled')]
            cancelled = self.seed(db, status='queued')
            db.add(DownloadJobControl(job_id=cancelled.id, owner_id='owner', cancelled=True, position=0))
            db.commit()
            for job in others:
                self.ready(job)
            result = self.queue.create(db, 'owner', ['BaW_jenozKc'], 'mp3', 1080)
            self.assertNotIn(result[0].id, [job.id for job in others] + [cancelled.id])

    def test_ready_file_preferred_over_newer_queued_job(self):
        with Session(self.engine) as db:
            old = self.seed(db, created_at=datetime.utcnow() - timedelta(hours=1))
            self.ready(old)
            self.seed(db, status='queued')
            result = self.queue.create(db, 'owner', [old.video_id], 'mp3', 1080)
            self.assertEqual(result[0].id, old.id)


if __name__ == '__main__':
    unittest.main()
