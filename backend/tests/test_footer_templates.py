import unittest
from app.api.footer_templates import replace_footer, safe_link_block


class FooterTemplatesTest(unittest.TestCase):
    def test_preserves_exact_composer_institution_follow_and_event_text(self):
        follow = "SIGA A FILARMÔNICA União Sanfelixta\nhttps://instagram.com/exemplo"
        biography = "Sobre o compositor: Tertuliano Santos\nMeu texto EXATO. Fonte: https://example.com"
        event = "Esta execução ocorreu no dia do samba. Veja https://example.com/evento"
        institution = "Sobre a filarmônica: Seu texto original."
        old = "🎺 Projeto Retreta — Só RARIDADES!\n\n1️⃣ https://www.youtube.com/playlist?list=OLD"
        new = "🎺 Projeto Retreta — Só RARIDADES!\n\n1️⃣ https://www.youtube.com/playlist?list=NEW"
        result, warning = replace_footer("\n\n".join([follow, biography, event, institution, old]), new)
        self.assertTrue(result.startswith(follow))
        for exact in (biography, event, institution):
            self.assertIn(exact, result)
        self.assertNotIn("list=OLD", result)
        self.assertEqual(result.count("list=NEW"), 1)

    def test_append_without_deleting_prose_or_unknown_link_blocks(self):
        original = "Texto com links e curiosidades: https://example.com\n\nMinha referência de estudo."
        result, warning = replace_footer(original, "Playlists\n\nhttps://www.youtube.com/playlist?list=X")
        self.assertTrue(result.startswith(original + "\n\n"))
        self.assertIn("acrescentado", warning)

    def test_refuses_biography_and_follow_as_replaceable_block(self):
        self.assertFalse(safe_link_block("Sobre o compositor: https://www.youtube.com/playlist?list=OLD"))
        self.assertFalse(safe_link_block("SIGA A FILARMÔNICA\nhttps://www.youtube.com/playlist?list=OLD"))
        self.assertFalse(safe_link_block("Um concerto histórico: https://www.youtube.com/playlist?list=OLD"))

    def test_idempotent_link_contents(self):
        template = "Projeto Retreta\n\n1️⃣ https://www.youtube.com/playlist?list=X"
        once, _ = replace_footer("Minha biografia.\n\nProjeto Retreta\n\nhttps://www.youtube.com/playlist?list=OLD", template)
        twice, _ = replace_footer(once, template)
        self.assertEqual(twice.count("list=X"), 1)
        self.assertIn("Minha biografia.", twice)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
