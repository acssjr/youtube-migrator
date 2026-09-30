import unittest

from app.services.description_service import propose


def video(id, title, description, date):
    return {"id": id, "snippet": {"title": title, "description": description, "publishedAt": date}}


class DescriptionTests(unittest.TestCase):
    def test_follow_filarmonica_precedes_biography_and_playlists(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        composer = video("composer", "Maxixe Chimarrão — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                         "Sobre o compositor: Tertuliano Santos foi maestro em Feira de Santana.", "2024")
        latest = video("latest", "Outra obra — Sociedade Filarmônica 25 de Março",
                       "Outra obra.\n\n👉🏻 Siga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\nPlaylists: https://youtube.com/current", "2025")
        result = propose(target, [target, composer, latest])
        description = result["description"]
        self.assertTrue(description.startswith("👉🏻 Siga a Filarmônica 25 de Março"))
        self.assertLess(description.index("Tertuliano Santos foi maestro"), description.index("Playlists:"))

    def test_complete_retreta_template_beats_newer_casarao_only_footer(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        full = video("full", "Marcha Eliana — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                     "Sobre o compositor: Tertuliano Santos foi maestro.\n\n👉🏻 Siga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\n🎶 Explore minhas playlists 👇\n\n🎺 Projeto Retreta — Só RARIDADES!\n\n1️⃣ https://www.youtube.com/playlist?list=RETRETA1\n\n2️⃣ https://www.youtube.com/playlist?list=RETRETA2\n\n3️⃣ https://www.youtube.com/watch?v=example&list=RETRETA3\n\n🎺 Projeto Música no Casarão 2024\n\n1️⃣ https://www.youtube.com/playlist?list=CASARAO1", "2026-04")
        sparse = video("sparse", "A Banda — Chico Buarque — Sociedade Filarmônica 25 de Março",
                       "Outra obra.\n\n👉🏻 Siga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\n🎺 Projeto Música no Casarão 2024\n\n1️⃣ https://www.youtube.com/playlist?list=CASARAO1", "2026-07")
        result = propose(target, [target, full, sparse])
        self.assertEqual(result["links_source"]["id"], "full")
        self.assertTrue(result["description"].startswith("👉🏻 Siga a Filarmônica"))
        for playlist_id in ("RETRETA1", "RETRETA2", "RETRETA3", "CASARAO1"):
            self.assertIn("playlist?list=" + playlist_id, result["description"])
        self.assertNotIn("watch?v=example", result["description"])

    def test_universal_retreta_section_adds_new_playlist_from_later_description(self):
        target = video("target", "Obra nova — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        full = video("full", "Marcha Eliana — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                     "Sobre o compositor: Tertuliano Santos foi maestro.\n\nSiga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\nProjeto Retreta\n\n1️⃣ https://youtube.com/playlist?list=RETRETA1\n\n2️⃣ https://youtube.com/playlist?list=RETRETA2\n\nProjeto Música no Casarão\n\n1️⃣ https://youtube.com/playlist?list=CASARAO1", "2025")
        new_link = video("new", "Outra obra — Sociedade Filarmônica 25 de Março",
                         "Projeto Retreta\n\n1️⃣ https://youtube.com/playlist?list=RETRETA3", "2026")
        result = propose(target, [target, full, new_link])
        self.assertIn("playlist?list=RETRETA3", result["description"])
        self.assertEqual(result["description"].count("playlist?list=RETRETA3"), 1)

    def test_channel_catalog_adds_fourth_and_fifth_nights_in_order(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        source = video("source", "Marcha Eliana — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                       "Sobre o compositor: Tertuliano Santos foi maestro.\n\nSiga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\nProjeto Retreta\n\n1️⃣ https://youtube.com/playlist?list=RETRETA1\n\n2️⃣ https://youtube.com/playlist?list=RETRETA2\n\n3️⃣ https://youtube.com/playlist?list=RETRETA3\n\nProjeto Música no Casarão\n\n1️⃣ https://youtube.com/playlist?list=CASARAO1", "2025")
        playlists = [
            {"id": f"RETRETA{night}", "snippet": {"title": f"Retreta – {night}ª Noite — Filarmônica 25 de Março"},
             "status": {"privacyStatus": "public"}} for night in (5, 3, 1, 4, 2)
        ]
        playlists += [
            {"id": "GUEST", "snippet": {"title": "Retreta – 4ª Noite — Filarmônica Lira Sangonçalense"},
             "status": {"privacyStatus": "public"}},
            {"id": "PRIVATE", "snippet": {"title": "Retreta – 6ª Noite — Filarmônica 25 de Março"},
             "status": {"privacyStatus": "private"}},
        ]
        result = propose(target, [target, source], playlists=playlists)
        description = result["description"]
        self.assertTrue(description.startswith("Siga a Filarmônica 25 de Março"))
        positions = [description.index(f"playlist?list=RETRETA{night}") for night in range(1, 6)]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1], description.index("Projeto Música no Casarão"))
        self.assertNotIn("GUEST", description)
        self.assertNotIn("PRIVATE", description)

    def test_channel_catalog_creates_retreta_section_when_old_footer_lacks_it(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        source = video("source", "Marcha Eliana — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                       "Sobre o compositor: Tertuliano Santos foi maestro.\n\nSiga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\nProjeto Música no Casarão\n\n1️⃣ https://youtube.com/playlist?list=CASARAO1", "2025")
        playlists = [{"id": "RETRETA4", "snippet": {"title": "Retreta – 4ª Noite — Filarmônica 25 de Março"},
                      "status": {"privacyStatus": "public"}}]
        description = propose(target, [target, source], playlists=playlists)["description"]
        self.assertLess(description.index("Projeto Retreta"), description.index("Projeto Música no Casarão"))
        self.assertIn("playlist?list=RETRETA4", description)

    def test_same_work_uses_newest_links(self):
        target = video("target", "O Navio Negreiro - Projeto Retreta", "", "2026")
        old = video("old", "O Navio Negreiro - Concerto", "História desta obra.\n\nMúsica no Casarão: 40 músicas em 4 apresentações\n\nPlaylists: https://youtube.com/old", "2020")
        new = video("new", "Outra peça", "Outra obra.\n\nProjeto Retreta: vídeos recentes\n\nPlaylists: https://youtube.com/new", "2025")
        result = propose(target, [target, old, new])
        self.assertEqual(result["match_type"], "same_work")
        self.assertIn("História desta obra", result["description"])
        self.assertIn("https://youtube.com/new", result["description"])
        self.assertNotIn("https://youtube.com/old", result["description"])
        self.assertNotIn("40 músicas", result["description"])
        self.assertIn("Projeto Retreta: vídeos recentes", result["description"])

    def test_composer_match_does_not_copy_other_work(self):
        target = video("target", "Senhora Santana", "", "2026")
        other = video("other", "Outra marcha", "Sobre o compositor: Antônio Silva foi compositor baiano.\n\nA Outra marcha fala de outro tema.", "2025")
        result = propose(target, [target, other], {"composer": "Antônio Silva"})
        self.assertEqual(result["match_type"], "composer")
        self.assertNotIn("outro tema", result["description"])

    def test_arranger_match_only_copies_credit(self):
        target = video("target", "Obra inédita", "", "2026")
        other = video("other", "Outra obra | Arr. Antonio Neves", "Curiosidade exclusiva da Outra obra.", "2025")
        result = propose(target, [target, other], {"arranger": "Antonio Neves"})
        self.assertEqual(result["match_type"], "arranger")
        self.assertEqual(result["description"], "Arranjo: Antonio Neves")

    def test_arranger_match_reuses_biography_without_other_work_curiosity(self):
        target = video("target", "Coisa Nº 1 — Moacir Santos (Arr. Antonio Neves) — Sociedade Filarmônica 25 de Março", "", "2026")
        source = video("source", "A Banda — Chico Buarque (Arr. Antonio Neves) — Sociedade Filarmônica 25 de Março",
                       "Curiosidade: A Banda foi composta para um festival.\n\nSobre o arranjador: Antonio Neves é maestro da Sociedade Filarmônica 25 de Março e professor de música.", "2025")
        result = propose(target, [target, source])
        self.assertEqual(result["match_type"], "arranger")
        self.assertIn("Antonio Neves é maestro", result["description"])
        self.assertNotIn("festival", result["description"])

    def test_title_middle_credit_finds_composer_and_ignores_other_ensemble_links(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        composer = video("composer", "Valsa Lindaura — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                         "Sobre o compositor: Tertuliano Santos foi maestro e compositor da filarmônica.\n\nPlaylists: https://youtube.com/own", "2025")
        unrelated = video("other", "Bolero — Heráclio Guerreiro — Filarmônica Terpsícore Popular",
                          "Outro repertório.\n\nPlaylists: https://youtube.com/unrelated", "2026")
        result = propose(target, [target, composer, unrelated])
        self.assertEqual(result["match_type"], "composer")
        self.assertIn("Tertuliano Santos foi maestro", result["description"])
        self.assertIn("https://youtube.com/own", result["description"])
        self.assertNotIn("https://youtube.com/unrelated", result["description"])

    def test_same_work_with_genre_and_number_variation(self):
        target = video("target", 'Dobrado Nº 155 "O Navio Negreiro" — Tranquilino Bastos — Sociedade Filarmônica 25 de Março', "", "2026")
        source = video("source", "O Navio Negreiro — Tranquilino Bastos — Sociedade Filarmônica 25 de Março",
                       "A história desta obra foi documentada no acervo.", "2024")
        result = propose(target, [target, source])
        self.assertEqual(result["match_type"], "same_work")
        self.assertEqual(result["source"]["id"], "source")

    def test_senhora_santanna_uses_published_composer_paragraph_not_event_text(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        chimarrao = video("chimarrao", "Maxixe Chimarrão — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                          'No dia do samba (02 de dezembro) a "Vinte e Cinco" traz esse belo maxixe do professor Santos, importante maestro da cidade de Feira de Santana, com passagens pela Filarmônica Vitória (40 anos como regente) e pela Filarmônica 25 de Março, deixando essa peça, além de diversas outras no acervo.\n\n👉🏻 Siga a Filarmônica Terpsícore Popular: https://instagram.com/terpsicore', "2023")
        copyright_note = video("copyright", "Marcha Eliana Meireles — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                               "©️ Esta partitura pertence ao acervo da Sociedade Filarmônica 25 de Março. Edição feita a partir dos autógrafos de Tertuliano Santos.", "2025")
        biography = "👨🏽‍🏫 Sobre o compositor: Tertuliano Ferreira Santos foi maestro e compositor da Sociedade Filarmônica 25 de Março."
        bio_source = video("bio", "Fantasia Céu Azul — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                           biography, "2024")
        hashtags = video("hashtags", "Marcha recente — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                         "#filarmonica25demarco #musica #maestro #tertulianosantos #anos30", "2026")
        latest_links = video("links", "A Banda — Chico Buarque — Sociedade Filarmônica 25 de Março",
                             "Outra obra.\n\n👉🏻 Siga a Filarmônica 25 de Março: https://instagram.com/filarmonica25demarco\n\nPlaylists: https://youtube.com/current", "2026")
        result = propose(target, [target, chimarrao, copyright_note, bio_source, hashtags, latest_links])
        self.assertEqual(result["match_type"], "composer")
        self.assertEqual(result["source"]["id"], "bio")
        self.assertIn(biography, result["description"])
        self.assertIn("https://youtube.com/current", result["description"])
        for excluded in ("dia do samba", "Chimarrão", "essa peça", "Terpsícore", "©", "#maestro"):
            self.assertNotIn(excluded, result["description"])

    def test_chimarrao_reuse_removes_old_event_and_copies_published_biography(self):
        target = video("target", "Maxixe Chimarrão — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        old = video("old", "Maxixe Chimarrão — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                    'No dia do samba (02 de dezembro) a "Vinte e Cinco" traz esse belo maxixe do professor Santos, importante maestro da cidade de Feira de Santana, com passagens pela Filarmônica Vitória (40 anos como regente) e pela Filarmônica 25 de Março, deixando essa peça, além de diversas outras no acervo.', "2023")
        bio = video("bio", "Fantasia Céu Azul — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                    "Sobre o compositor: Tertuliano Ferreira Santos foi maestro em Feira de Santana.", "2024")
        result = propose(target, [target, old, bio])
        self.assertEqual(result["match_type"], "composer")
        self.assertIn(bio["snippet"]["description"], result["description"])
        self.assertNotIn("dia do samba", result["description"].lower())
        self.assertNotIn("essa peça", result["description"])

    def test_composer_fallback_ignores_arranger_bio_that_mentions_composer_in_school_name(self):
        target = video("target", "Marcha Nº 7 — Estevam Moura — Sociedade Filarmônica 25 de Março", "", "2026")
        wrong = video("wrong", "A Banda — Chico Buarque (Arr. Antonio Neves) — Sociedade Filarmônica 25 de Março",
                      "🎼 Sobre o arranjador: Antonio Neves atua na Escola de Música Maestro Estevam Moura.", "2025")
        right = video("right", "Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março",
                      "👨🏽‍🏫 Sobre o compositor: Estevam Moura foi maestro e compositor da Sociedade Filarmônica 25 de Março.", "2024")
        result = propose(target, [target, wrong, right])
        self.assertEqual(result["source"]["id"], "right")
        self.assertIn("Estevam Moura foi maestro", result["description"])
        self.assertNotIn("Antonio Neves", result["description"])

    def test_composer_fallback_ignores_another_composers_bio_with_incidental_name(self):
        target = video("target", "Marcha Nº 7 — Estevam Moura — Sociedade Filarmônica 25 de Março", "", "2026")
        wrong = video("wrong", "Dobrado Grito dos Pretos — Amando Nobre — Sociedade Filarmônica 25 de Março",
                      "Sobre o compositor: Amando Nobre foi regente. Ao lado de Estevam Moura, integrou a cena musical.", "2025")
        right = video("right", "Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março",
                      "Sobre o compositor: Estevam Moura foi maestro e compositor da Sociedade Filarmônica 25 de Março.", "2024")
        result = propose(target, [target, wrong, right])
        self.assertEqual(result["source"]["id"], "right")
        self.assertNotIn("Amando Nobre", result["description"])

    def test_composer_biography_preserves_original_list_of_other_works(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos", "", "2026")
        source = video("source", "Fantasia Ibotirama — Tertuliano Santos",
                       "Sobre o compositor: Tertuliano Ferreira Santos foi um maestro de Feira de Santana. Conhecido como professor Santos, ele é autor de várias obras, incluindo a fantasia \"Ibotirama\" e o maxixe \"Chimarrão\".", "2024")
        result = propose(target, [target, source])
        self.assertEqual(result["match_type"], "composer")
        self.assertEqual(result["description"], source["snippet"]["description"])

    def test_newer_event_claim_never_beats_exact_published_composer_text(self):
        target = video("target", "Marcha Senhora Sant'Anna — Tertuliano Santos", "", "2026")
        original = "👨🏽‍🏫 Sobre o compositor: Tertuliano Ferreira Santos foi um maestro e compositor que dirigiu a Sociedade Filarmônica 25 de Março em Feira de Santana, Bahia. Conhecido como professor Santos, ele é autor de várias obras, incluindo a Fantasia \"Ibotirama\" e o maxixe \"Chimarrão\"."
        bio = video("bio", "Fantasia Céu Azul — Tertuliano Santos", original, "2024")
        event = video("event", "Maxixe Chimarrão — Tertuliano Santos",
                      "No dia do samba a banda toca o maxixe do professor Santos, importante maestro da cidade.", "2026")
        result = propose(target, [target, event, bio])
        self.assertEqual(result["description"], original)
        self.assertEqual(result["source"]["id"], "bio")

    def test_old_same_work_removes_expired_promotion_and_stale_age(self):
        target = video("target", "Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março", "", "2026")
        source = video("source", "Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março",
                       "Sobre o compositor: Estevam Moura foi maestro.\n\n🎼 Oportunidade para crianças: inscreva-se!\n\n🌟 Sobre a Sociedade Filarmônica 25 de Março: Com 157 anos de história.\n\n🎶 Apaixonado por música de filarmônica? Explore minhas playlists 👇\n\n🎺 Projeto Música no Casarão 2024 [40 músicas]\n\n#musica #filarmonica #anos30", "2024")
        result = propose(target, [target, source])
        self.assertIn("Estevam Moura foi maestro", result["description"])
        for excluded in ("inscreva-se", "157 anos", "2024 [40", "#anos30"):
            self.assertNotIn(excluded, result["description"])

    def test_institution_is_reused_independently_from_work_and_playlist_references(self):
        target = video("target", "Marcha Nova — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        bio = video("bio", "Outra obra — Tertuliano Santos", "Sobre o compositor: Tertuliano Santos foi maestro.", "2026")
        text = "🌟 Sobre a Sociedade Filarmônica 25 de Março: Fundada em 1868 em Feira de Santana. Com mais de 157 anos de história, a instituição atua na comunidade."
        own = video("own", "A Banda — Sociedade Filarmônica 25 de Março", text, "2025")
        guest = video("guest", "Outra obra — Filarmônica Vitória", "Sobre a Sociedade Filarmônica Vitória: Visitou a Filarmônica 25 de Março.", "2026")
        result = propose(target, [target, bio, own, guest])
        self.assertIn("Fundada em 1868", result["description"])
        self.assertIn("Ao longo de sua história, a instituição", result["description"])
        self.assertNotIn("157 anos", result["description"])
        self.assertNotIn("Visitou", result["description"])
        self.assertEqual(result["institution_source"]["id"], "own")
        self.assertEqual(result["source"]["id"], "bio")

    def test_institution_is_not_duplicated_when_same_work_contains_it(self):
        target = video("target", "Marcha Nova — Tertuliano Santos — Sociedade Filarmônica 25 de Março", "", "2026")
        text = "Sobre o compositor: Tertuliano Santos foi maestro.\n\nSobre a Sociedade Filarmônica 25 de Março: Fundada em 1868.\n\nPlaylists: https://youtube.com/current"
        source = video("source", target["snippet"]["title"], text, "2025")
        result = propose(target, [target, source])
        self.assertEqual(result["description"].count("Sobre a Sociedade Filarmônica"), 1)
        self.assertLess(result["description"].index("Sobre a Sociedade"), result["description"].index("Playlists"))

    def test_institution_matches_abbreviated_ensemble_title(self):
        target = video("target", "Obra Nova — Tertuliano Santos — S.F. 25 de Março", "", "2026")
        source = video("source", "Outra obra — Tertuliano Santos — Sociedade Filarmônica 25 de Março",
                       "Sobre o compositor: Tertuliano Santos foi maestro.\n\nSobre a Sociedade Filarmônica 25 de Março: Fundada em 1868.", "2025")
        self.assertIn("Fundada em 1868", propose(target, [target, source])["description"])


if __name__ == "__main__":
    unittest.main()
