import unittest
from app.api.work_catalog import suggestions, title_suggestion


class WorkCatalogTests(unittest.TestCase):
    def video(self, identifier, title):
        return {"id": identifier, "snippet": {"title": title, "description": "Sobre o compositor: Outro Nome foi..."}}

    def test_title_roles_and_no_biography_guess(self):
        item = title_suggestion(self.video("one", "Dobrado Allah — Estevam Moura — Arr. Antonio Neves — Sociedade Filarmônica 25 de Março"))
        self.assertEqual((item["name"], item["genre"], item["composer"], item["arranger"]), ("Allah", "Dobrado", "Estevam Moura", "Antonio Neves"))
        unknown = title_suggestion(self.video("two", "Senhora Sant’anna — Sociedade Filarmônica União Sanfelixta"))
        self.assertEqual(unknown["composer"], "")

    def test_grouping_keeps_authors_distinct_and_sources(self):
        result = suggestions([self.video("a", "Valsa Aurora — João Silva"), self.video("b", "Valsa Aurora — João Silva"), self.video("c", "Valsa Aurora — José Silva")])
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted(len(item["sources"]) for item in result), [1, 2])

    def test_single_title_preserved_as_unconfirmed_work(self):
        item = title_suggestion(self.video("x", "Apresentação especial em 2023"))
        self.assertEqual(item["name"], "Apresentação especial em 2023")
        self.assertEqual(item["genre"], "")
        self.assertEqual(item["composer"], "")
