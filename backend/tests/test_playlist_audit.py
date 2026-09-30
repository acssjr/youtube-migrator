import unittest
from unittest.mock import Mock
from app.api.playlist_audit import audit_playlists


class AuditTests(unittest.TestCase):
    def test_pages_duplicates_unavailable_private_and_expected(self):
        service = Mock()
        service.list_playlists.return_value = [
            {"id": "p1", "snippet": {"title": "Retreta"}},
            {"id": "p2", "snippet": {"title": " RETRETA "}},
        ]
        service.list_all_video_resources.return_value = [{"id":"a","snippet":{"title":"Allah"}}, {"id":"outside","snippet":{"title":"Fora"}}]
        first, second, empty = Mock(), Mock(), Mock()
        def item(key, video, position):
            return {"id":key,"snippet":{"title":"Vídeo","position":position},"contentDetails":{"videoId":video}}
        first.execute.return_value = {"items":[item("i1","a",0)],"nextPageToken":"next"}
        second.execute.return_value = {"items":[item("i2","a",1),item("i3","gone",2)]}
        empty.execute.return_value = {"items":[]}
        service.youtube.playlistItems().list.side_effect = [first, empty]
        service.youtube.playlistItems().list_next.side_effect = [second, None, None]
        service.youtube.videos().list().execute.return_value = {"items":[{"id":"a","snippet":{"title":"Allah"},"status":{"privacyStatus":"private"}}]}
        report = audit_playlists(service, [{"playlist_url":"https://www.youtube.com/playlist?list=p1","video_ids":["a","expected"]}])
        result = report["playlists"][0]
        self.assertEqual(result["duplicate_count"],1)
        self.assertEqual(result["private_count"],2)
        self.assertEqual(result["unavailable_count"],1)
        self.assertEqual(result["missing_expected"],["expected"])
        self.assertEqual([i["item_id"] for i in result["items"]],["i1","i2","i3"])
        self.assertEqual([i["position"] for i in result["items"]],[0,1,2])
        self.assertTrue(result["duplicate_title"])
        self.assertTrue(report["playlists"][1]["empty"])
        self.assertEqual(report["unassigned"],[{"id":"outside","title":"Fora"}])
        service.youtube.playlistItems().delete.assert_not_called()
        service.youtube.playlistItems().insert.assert_not_called()

    def test_no_playlists_reports_channel_inventory(self):
        service = Mock()
        service.list_playlists.return_value = []
        service.list_all_video_resources.return_value = [{"id":"a","snippet":{"title":"Allah"}}]
        report = audit_playlists(service)
        self.assertEqual(report["video_count"],1)
        self.assertEqual(len(report["unassigned"]),1)
        service.youtube.playlistItems.assert_not_called()
