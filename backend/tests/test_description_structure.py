import unittest
from types import SimpleNamespace
from app.services.description_structure import attach_structure

class StructureTests(unittest.TestCase):
    def test_removes_foreign_archive_and_uses_universal_footer_without_music(self):
        videos=[{"id":"old", "snippet":{"title":"Dobrado — Autor — Sociedade Filarmônica 25 de Março", "publishedAt":"2026-01-01", "description":"Siga a Filarmônica 25 de Março nas suas redes sociais:\nhttps://instagram.com/main\n\n🎺 Projeto Retreta — Só RARIDADES!\n\n1️⃣ https://www.youtube.com/playlist?list=night1"}}]
        proposal={"title":"Marcha Cecí — Almiro Oliveira — Sociedade Filarmônica União Sanfelixta", "description":"© Esta partitura pertence ao acervo da Minerva Cachoeirana."}
        result=attach_structure(proposal,videos,[],[])["structure"]
        self.assertEqual(result["ensemble"],"Sociedade Filarmônica União Sanfelixta")
        self.assertEqual(result["body"],"")
        self.assertIn('night1',result['playlists'])
        self.assertIn('25 de Março',result['main_follow'])

    def test_exact_preset_history_and_approved_bio_with_url_are_preserved(self):
        bio='Sobre o compositor: Tertuliano Santos — TEXTO EXATO https://example.com'
        preset=SimpleNamespace(payload={"name":"Sociedade Filarmônica União Sanfelixta", "institutionalText":"Sobre a instituição: Com 100 anos de história, TEXTO EXATO.","socialLinks":"Texto exato das redes"})
        result=attach_structure({"title":"Obra — Autor — Sociedade Filarmônica União Sanfelixta", "description":bio},[],[],[preset])["structure"]
        self.assertEqual(result['body'],bio)
        self.assertEqual(result['history'],preset.payload['institutionalText'])
        self.assertEqual(result['social_text'],preset.payload['socialLinks'])
