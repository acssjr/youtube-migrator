import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from app.api.archive_backup import router, FORMAT, csv_cell
from app.database.db import get_session
from app.models.acervo_models import AcervoRecord, AcervoRecordVersion
from app.models.revision_models import MetadataRevision


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        app = FastAPI(); app.include_router(router, prefix='/api')
        def db():
            with Session(self.engine) as session:
                yield session
        app.dependency_overrides[get_session] = db
        self.client = TestClient(app)
        self.owner = patch('app.api.archive_backup.acervo_owner', return_value='mine'); self.owner.start()

    def tearDown(self):
        self.owner.stop(); self.client.close(); self.engine.dispose()

    def archive(self):
        return {'format': FORMAT, 'version': 1, 'records': [{'id':'source', 'kind':'approved_text', 'payload':{'text':'Sobre o compositor:\n  Texto EXATO.\n'}}], 'record_versions':[{'record_id':'source','kind':'approved_text','payload':{'text':'Anterior'}}]}

    def test_preview_is_read_only_then_import_exact_and_skip_duplicates(self):
        body = {'archive':self.archive()}
        preview = self.client.post('/api/archive-backup/import', json=body).json()
        self.assertEqual(preview['new_records'], 1)
        with Session(self.engine) as db:
            self.assertEqual(db.exec(select(AcervoRecord)).all(), [])
        result = self.client.post('/api/archive-backup/import', json=dict(body, confirm=True)).json()
        self.assertTrue(result['imported'])
        with Session(self.engine) as db:
            record = db.exec(select(AcervoRecord)).one()
            self.assertNotEqual(record.id, 'source')
            self.assertEqual(record.owner_id, 'mine')
            self.assertEqual(record.payload['text'], 'Sobre o compositor:\n  Texto EXATO.\n')
            self.assertEqual(db.exec(select(AcervoRecordVersion)).one().record_id, record.id)
        duplicate = self.client.post('/api/archive-backup/import', json=dict(body, confirm=True)).json()
        self.assertEqual(duplicate['new_records'], 0)
        self.assertEqual(duplicate['historical_versions'], 0)

    def test_export_scoped_and_sanitized(self):
        with Session(self.engine) as db:
            db.add(AcervoRecord(owner_id='mine', kind='note', payload={'text':'Mine','token':'secret'}))
            db.add(AcervoRecord(owner_id='someone-else', kind='note', payload={'text':'Other'}))
            db.add(MetadataRevision(owner_id='mine', channel_id='channel', video_id='video', before_snippet={'description':'Exato antes'}, after_snippet={'description':'Exato depois'}))
            db.add(MetadataRevision(owner_id='someone-else', channel_id='channel', video_id='other', before_snippet={'description':'Outro dono'}))
            db.commit()
        response = self.client.get('/api/archive-backup/export')
        self.assertEqual(response.status_code, 200)
        content = response.json()
        self.assertEqual(len(content['records']), 1)
        self.assertNotIn('owner_id', response.text)
        self.assertNotIn('secret', response.text)
        self.assertNotIn('Other', response.text)
        self.assertEqual(len(content['metadata_revisions']), 1)
        self.assertEqual(content['metadata_revisions'][0]['before_snippet']['description'], 'Exato antes')

    def test_credentials_unknown_kind_and_duplicate_ids_rejected(self):
        backup = self.archive(); backup['records'][0]['payload']['credentials'] = {'token':'x'}
        self.assertEqual(self.client.post('/api/archive-backup/import', json={'archive':backup}).status_code,422)
        backup = self.archive(); backup['records'][0]['kind'] = 'oauth'
        self.assertEqual(self.client.post('/api/archive-backup/import', json={'archive':backup}).status_code,422)
        backup = self.archive(); backup['records'].append(backup['records'][0])
        self.assertEqual(self.client.post('/api/archive-backup/import', json={'archive':backup}).status_code,422)

    def test_csv_formula_guard(self):
        self.assertEqual(csv_cell('=IMPORTXML("secret")'), "'=IMPORTXML(\"secret\")")
        self.assertEqual(csv_cell('  +1'), "'  +1")
        self.assertEqual(csv_cell('Sobre o compositor:\nTertuliano Santos'), 'Sobre o compositor:\nTertuliano Santos')

    def test_youtube_export_preserves_order_and_full_description(self):
        from unittest.mock import MagicMock
        service = MagicMock()
        service.list_all_video_resources.return_value = [{'id':'abcdefghijk'}]
        service.youtube.videos.return_value.list.return_value.execute.return_value = {'items':[{'id':'abcdefghijk', 'snippet':{'description':'Siga\n\nSobre o compositor: EXATO'}, 'status':{'privacyStatus':'unlisted'}}]}
        service.list_playlists.return_value = [{'id':'PLone','snippet':{'title':'Retreta'},'status':{'privacyStatus':'public'}}]
        service.playlist_video_ids.return_value = ['second','first','second']
        with patch('app.api.archive_backup.channel_service', return_value=service):
            exported = self.client.get('/api/archive-backup/export?channel_id=mine-channel').json()
        self.assertEqual(exported['playlists'][0]['video_ids'], ['second','first','second'])
        self.assertEqual(exported['videos'][0]['snippet']['description'], 'Siga\n\nSobre o compositor: EXATO')
