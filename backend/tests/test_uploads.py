import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from pydantic import ValidationError
from starlette.requests import Request

from app.api.uploads import AuthorizeUpload, PreviewUploads, UploadDraft, authorize, catalog, preview, published_person_name
from app.api.uploads import CreateBatchPlaylist, create_batch_playlist, ensemble_videos


def browser(origin="https://acervo.test"):
    return Request({"type": "http", "scheme": "https", "server": ("acervo.test", 443),
                    "path": "/api/uploads/authorize", "headers": [(b"host", b"acervo.test"), (b"origin", origin.encode())], "query_string": b""})


class UploadTests(unittest.TestCase):
    def test_ensemble_search_matches_title_accents_and_ignores_description_mentions(self):
        service = Mock()
        service.list_all_video_resources.return_value = [
            {"id": "a", "snippet": {"title": "Marcha — Sociedade Filarmônica União Sanfelixta"}},
            {"id": "b", "snippet": {"title": "Dobrado - UNIAO SANFELIXTA"}},
            {"id": "other", "snippet": {"title": "Marcha — 25 de Março", "description": "União Sanfelixta"}},
            {"id": "partial", "snippet": {"title": "União SanfelixtaXYZ"}},
        ]
        with patch("app.api.uploads.channel_service", return_value=service):
            result = ensemble_videos("c", "Sociedade Filarmônica União Sanfelixta", browser(), Response(), None)
        self.assertEqual([item["id"] for item in result], ["a", "b"])

    def test_new_playlist_adds_videos_before_final_verification(self):
        service = Mock()
        service.list_playlists.return_value = [{"id": "ref", "snippet": {"title": "Reference"}}]
        service.list_all_video_resources.return_value = [{"id": "a"}]
        service.create_playlist.return_value = "new"
        service.playlist_video_ids.return_value = ["a"]
        payload = CreateBatchPlaylist(channel_id="c", reference_id="ref", title="New", video_ids=["a"], privacy="public")
        with patch("app.api.uploads.channel_service", return_value=service):
            result = create_batch_playlist(payload, browser(), None)
        service.create_playlist.assert_called_once_with("New", privacy_status="public")
        service.playlist_video_ids.assert_called_once_with("new")
        service.add_video_to_playlist.assert_called_once_with("new", "a")
        self.assertTrue(result["complete"])

    def test_playlist_validates_video_ownership_before_creating(self):
        service = Mock()
        service.list_playlists.return_value = [{"id": "ref", "snippet": {"title": "Reference"}}]
        service.list_all_video_resources.return_value = []
        payload = CreateBatchPlaylist(channel_id="c", reference_id="ref", title="New", video_ids=["foreign"])
        with patch("app.api.uploads.channel_service", return_value=service), self.assertRaises(HTTPException):
            create_batch_playlist(payload, browser(), None)
        service.create_playlist.assert_not_called()

    def test_playlist_retry_reuses_playlist_and_skips_existing_videos(self):
        service = Mock()
        service.list_playlists.return_value = [{"id": "ref", "snippet": {"title": "Reference"}}, {"id": "existing", "snippet": {"title": "New"}}]
        service.list_all_video_resources.return_value = [{"id": "a"}, {"id": "b"}]
        service.playlist_video_ids.side_effect = [["a"], ["a", "b"]]
        payload = CreateBatchPlaylist(channel_id="c", reference_id="ref", title="New", video_ids=["a", "b"])
        with patch("app.api.uploads.channel_service", return_value=service):
            result = create_batch_playlist(payload, browser(), None)
        service.create_playlist.assert_not_called()
        service.add_video_to_playlist.assert_called_once_with("existing", "b")
        self.assertTrue(result["complete"])

    def test_authorization_rejects_another_origin_before_reading_tokens(self):
        with patch("app.api.uploads.channel_service") as service:
            with self.assertRaises(HTTPException) as error:
                authorize(AuthorizeUpload(channel_id="channel"), browser("https://other.test"), Response(), None)
            self.assertEqual(error.exception.status_code, 403)
            service.assert_not_called()

    def test_authorization_refreshes_and_returns_only_temporary_bearer(self):
        credentials = SimpleNamespace(scopes=["https://www.googleapis.com/auth/youtube.upload"],
                                      refresh_token="private-refresh", token="temporary-token", refresh=Mock())
        response = Response()
        with patch("app.api.uploads.channel_service", return_value=SimpleNamespace(credentials=credentials)):
            result = authorize(AuthorizeUpload(channel_id="channel"), browser(), response, None)
        credentials.refresh.assert_called_once()
        self.assertEqual(result, {"access_token": "temporary-token"})
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_channel_ownership_failure_is_propagated(self):
        with patch("app.api.uploads.channel_service", side_effect=HTTPException(403, "foreign channel")):
            with self.assertRaises(HTTPException) as error:
                authorize(AuthorizeUpload(channel_id="foreign"), browser(), Response(), None)
            self.assertEqual(error.exception.status_code, 403)

    def test_missing_upload_scope_requires_reconnection(self):
        with patch("app.api.uploads.channel_service", return_value=SimpleNamespace(credentials=SimpleNamespace(scopes=[]))):
            with self.assertRaises(HTTPException) as error:
                authorize(AuthorizeUpload(channel_id="channel"), browser(), Response(), None)
            self.assertEqual(error.exception.status_code, 403)

    def test_preview_reuses_acervo_and_identity_without_publishing(self):
        service = Mock()
        service.list_all_video_resources.return_value = [{"id": "existing"}]
        service.list_playlists.return_value = []
        payload = PreviewUploads(channel_id="channel", items=[UploadDraft(id="local", title="Marcha Nova", identity={"composer": "Autor Existente"})])
        with patch("app.api.uploads.channel_service", return_value=service), patch("app.api.uploads.propose", return_value={"description": "original"}) as proposal:
            self.assertEqual(preview(payload, browser(), None), [{"description": "original"}])
        self.assertEqual(proposal.call_args.args[0]["id"], "local")
        self.assertEqual(proposal.call_args.args[2]["composer"], "Autor Existente")
        service.update_video_description.assert_not_called()

    def test_catalog_uses_existing_spelling(self):
        service = Mock()
        service.list_all_video_resources.return_value = [{"id": "v", "snippet": {"title": "Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março", "description": ""}}]
        with patch("app.api.uploads.channel_service", return_value=service):
            result = catalog("channel", browser(), Response(), None)
        self.assertEqual(result["composers"], ["Estevam Moura"])
        self.assertEqual(result["ensembles"], ["Sociedade Filarmônica 25 de Março"])

    def test_invalid_title_and_oversized_batch_rejected(self):
        for title in [" ", "<invalid>", "x" * 101]:
            with self.assertRaises(ValidationError):
                UploadDraft(id="local", title=title)
        with self.assertRaises(ValidationError):
            PreviewUploads(channel_id="channel", items=[UploadDraft(id=str(i), title="Title") for i in range(51)])

    def test_catalog_does_not_turn_biographies_into_names(self):
        self.assertEqual(published_person_name("Tertuliano Ferreira Santos foi um maestro e compositor."), "Tertuliano Ferreira Santos")
        self.assertEqual(published_person_name("Waldemar da Paixão, compositor e regente, teve atuação…"), "Waldemar da Paixão")
        self.assertEqual(published_person_name('Francisco "Chico" Buarque de Hollanda é um compositor.'), 'Francisco "Chico" Buarque de Hollanda')
        self.assertEqual(published_person_name("es de bandas do Brasil, A.M. do Espírito Santo, interpretado…"), "")
        self.assertEqual(published_person_name(", multi instrumentista, nascido em…"), "")
