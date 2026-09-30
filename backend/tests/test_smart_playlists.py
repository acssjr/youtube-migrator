import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException, Response
from starlette.requests import Request
from app.api.smart_playlists import Criteria, Preview, Publish, preview, publish, video_matches


class SmartPlaylistsTests(unittest.TestCase):
    def setUp(self):
        self.request = Request({"type": "http", "headers": []})
        self.service = Mock()
        self.video = {"id": "v1", "snippet": {"title": "Dobrado Allah — Estevam Moura — Sociedade Filarmônica União Sanfelixta", "description": "Outra filarmônica Terpsícore Popular"}}
        self.service.list_all_video_resources.return_value = [self.video, self.video]
        self.service.list_playlists.return_value = []
        self.service.create_playlist.return_value = "p1"
        self.service.playlist_video_ids.return_value = []
        self.stub = patch("app.api.smart_playlists.channel_service", return_value=self.service)
        self.stub.start()

    def tearDown(self):
        self.stub.stop()

    def test_combines_exact_credits_and_ignores_biography_mentions(self):
        self.assertTrue(video_matches(self.video, Criteria(work="Allah", composer="Estevam Moura", ensemble="União Sanfelixta", genre="Dobrado")))
        self.assertFalse(video_matches(self.video, Criteria(composer="Estevam")))
        self.assertFalse(video_matches(self.video, Criteria(ensemble="Terpsícore Popular")))
        self.assertFalse(video_matches(self.video, Criteria(genre="Marcha")))

    def test_preview_deduplicates_without_writes(self):
        result = preview(Preview(channel_id="channel"), self.request, Response(), None)
        self.assertEqual(len(result["videos"]), 1)
        self.service.create_playlist.assert_not_called()
        self.service.add_video_to_playlist.assert_not_called()

    def test_rejects_changed_match_or_foreign_video_before_writes(self):
        with self.assertRaises(HTTPException) as caught:
            publish(Publish(channel_id="channel", title="Meu repertório", video_ids=["foreign"]), self.request, None)
        self.assertEqual(caught.exception.status_code, 409)
        self.service.create_playlist.assert_not_called()

    def test_existing_playlist_must_be_owned(self):
        with self.assertRaises(HTTPException) as caught:
            publish(Publish(channel_id="channel", title="Lista", playlist_id="foreign", video_ids=["v1"]), self.request, None)
        self.assertEqual(caught.exception.status_code, 403)

    def test_retry_skips_existing_and_reports_each_error(self):
        other = {"id": "v2", "snippet": {"title": "Marcha Esperança — João Silva"}}
        self.service.list_all_video_resources.return_value = [self.video, other]
        self.service.list_playlists.return_value = [{"id": "p1", "snippet": {"title": "Minha lista"}}]
        self.service.playlist_video_ids.return_value = ["v1"]
        self.service.add_video_to_playlist.side_effect = Exception("sensitive api data")
        result = publish(Publish(channel_id="channel", title="Lista", playlist_id="p1", video_ids=["v1", "v2", "v2"]), self.request, None)
        self.assertEqual([i["status"] for i in result["items"]], ["existing", "error"])
        self.assertFalse(result["complete"])
        self.service.add_video_to_playlist.assert_called_once_with("p1", "v2")
        self.assertNotIn("sensitive", str(result))

    def test_same_title_requires_explicit_existing_choice(self):
        self.service.list_playlists.return_value = [{"id": "p1", "snippet": {"title": "Lista"}}]
        with self.assertRaises(HTTPException) as caught:
            publish(Publish(channel_id="channel", title="Lista", video_ids=["v1"]), self.request, None)
        self.assertEqual(caught.exception.status_code, 409)
        self.service.create_playlist.assert_not_called()

    def test_creation_preserves_selection_order_deduplicated(self):
        other = {"id": "v2", "snippet": {"title": "Marcha Esperança — João Silva"}}
        self.service.list_all_video_resources.return_value = [self.video, other]
        result = publish(Publish(channel_id="channel", title="Lista", video_ids=["v2", "v1", "v2"]), self.request, None)
        self.assertTrue(result["complete"])
        self.assertEqual([i["video_id"] for i in result["items"]], ["v2", "v1"])
        self.service.create_playlist.assert_called_once_with("Lista", privacy_status="private")
