import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from starlette.requests import Request
from app.models.revision_models import MetadataRevision
from app.api.revisions import Preview, Apply, preview, apply, restore, publish_revision


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.service = Mock()
        self.video = {"id": "v", "snippet": {"channelId": "channel", "title": "Original",
                      "description": "Sobre o compositor: texto EXATO\n", "categoryId": "10",
                      "tags": ["música"], "defaultLanguage": "pt", "defaultAudioLanguage": "pt"}}
        self.service.get_video_resource.return_value = self.video
        self.request = Request({"type": "http", "headers": []})
        self.patch_service = patch("app.api.revisions.channel_service", return_value=self.service)
        self.patch_cloud = patch("app.api.revisions.cloud_mode", return_value=False)
        self.patch_service.start()
        self.patch_cloud.start()

    def tearDown(self):
        self.patch_service.stop()
        self.patch_cloud.stop()
        self.session.close()
        self.engine.dispose()

    def draft(self):
        return preview(Preview(channel_id="channel", items=[{"video_id": "v", "description": "Novo texto\n"}]), self.request, self.session)[0]

    def test_preview_does_not_publish_and_retains_exact_text(self):
        revision = self.draft()
        self.service.youtube.videos.assert_not_called()
        self.assertEqual(revision.before_snippet["description"], self.video["snippet"]["description"])
        self.assertEqual(revision.after_snippet["description"], "Novo texto\n")

    def test_snapshot_is_committed_before_youtube_write_and_preserves_fields(self):
        def execute():
            stored = self.session.exec(select(MetadataRevision)).first()
            self.assertEqual(stored.status, "pending")
            self.assertEqual(stored.before_snippet["tags"], ["música"])
        self.service.youtube.videos.return_value.update.return_value.execute.side_effect = execute
        revision = publish_revision(self.session, self.service, "channel", "local", self.video, "Novo texto\n")
        self.assertEqual(revision.status, "applied")
        sent = self.service.youtube.videos.return_value.update.call_args.kwargs["body"]["snippet"]
        self.assertNotIn("channelId", sent)
        self.assertEqual(sent["defaultAudioLanguage"], "pt")
        self.assertEqual(sent["description"], "Novo texto\n")

    def test_apply_rejects_video_changed_since_preview(self):
        revision = self.draft()
        self.video["snippet"]["description"] = "Alterado fora do app"
        with self.assertRaises(HTTPException) as error:
            apply(Apply(channel_id="channel", revision_ids=[revision.id]), self.request, self.session)
        self.assertEqual(error.exception.status_code, 409)
        self.service.youtube.videos.assert_not_called()

    def test_restore_rejects_changes_after_publication(self):
        revision = publish_revision(self.session, self.service, "channel", "local", self.video, "Novo")
        self.service.youtube.reset_mock()
        with self.assertRaises(HTTPException) as error:
            restore("channel", revision.id, self.request, self.session)
        self.assertEqual(error.exception.status_code, 409)
        self.service.youtube.videos.assert_not_called()

    def test_restore_publishes_old_version_and_records_rollback(self):
        revision = publish_revision(self.session, self.service, "channel", "local", self.video, "Novo")
        self.service.get_video_resource.return_value = {"id": "v", "snippet": dict(revision.after_snippet, channelId="channel")}
        rollback = restore("channel", revision.id, self.request, self.session)
        self.assertEqual(revision.status, "restored")
        self.assertEqual(rollback.restores_id, revision.id)
        self.assertEqual(rollback.after_snippet["description"], "Sobre o compositor: texto EXATO\n")

    def test_foreign_video_is_rejected(self):
        self.video["snippet"]["channelId"] = "other"
        with self.assertRaises(HTTPException) as error:
            self.draft()
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.session.exec(select(MetadataRevision)).all(), [])

    def test_failed_publication_keeps_snapshot(self):
        self.service.youtube.videos.return_value.update.return_value.execute.side_effect = RuntimeError("network")
        with self.assertRaises(RuntimeError):
            publish_revision(self.session, self.service, "channel", "local", self.video, "Novo")
        stored = self.session.exec(select(MetadataRevision)).one()
        self.assertEqual(stored.status, "failed")
        self.assertEqual(stored.before_snippet["title"], "Original")

    def test_revision_belongs_to_owner(self):
        revision = self.draft()
        revision.owner_id = "another-owner"
        self.session.add(revision)
        self.session.commit()
        with self.assertRaises(HTTPException) as error:
            apply(Apply(channel_id="channel", revision_ids=[revision.id]), self.request, self.session)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
