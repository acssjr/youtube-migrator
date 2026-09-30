import unittest
from app.services.approved_texts import approved_for_identity, published_blocks, enrich_proposal


class ApprovedTextTests(unittest.TestCase):
    def test_exact_text_newest_approved_identity_only(self):
        original = 'Sobre o compositor: Tertuliano Santos\r\n  Texto meu.  '
        records = [
            {'id': 'wrong-role', 'updated_at': '2026-10-01', 'payload': {'role': 'arranger', 'name': 'Tertuliano Santos', 'text': 'errado', 'approved': True}},
            {'id': 'draft', 'updated_at': '2026-10-01', 'payload': {'role': 'composer', 'name': 'Tertuliano Santos', 'text': 'rascunho', 'approved': False}},
            {'id': 'chosen', 'updated_at': '2026-09-30', 'payload': {'role': 'composer', 'name': 'Tertuliano Santos', 'text': original, 'approved': True}},
            {'id': 'older', 'updated_at': '2025-01-01', 'payload': {'role': 'composer', 'name': 'Tertuliano Santos', 'text': 'antigo', 'approved': True}},
        ]
        found = approved_for_identity(records, {'composer': 'tertuliano santos'})
        self.assertEqual(found['composer']['text'], original)
        self.assertEqual(list(found), ['composer'])

    def test_accents_match_but_partial_name_never_matches(self):
        record = {'payload': {'role': 'composer', 'name': 'Antônio Neves', 'text': 'original', 'approved': True}}
        self.assertIn('composer', approved_for_identity([record], {'composer': 'Antonio Neves'}))
        self.assertEqual(approved_for_identity([record], {'composer': 'Neves'}), {})
        self.assertEqual(approved_for_identity([record], {'composer': ''}), {})

    def test_extract_preserves_passage_and_omits_other_work_event(self):
        original = 'Sobre o compositor: Tertuliano Santos\r\nTexto  original.  '
        description = 'Siga a Filarmônica\r\n\r\nHoje é dia do samba.\r\n\r\n' + original + '\r\n\r\nProjeto Retreta\r\nLink'
        self.assertEqual(published_blocks(description), [{'role': 'composer', 'text': original}])

    def test_enrich_preserves_exact_bio_follow_and_footer(self):
        exact = 'Sobre o compositor: Meu TEXTO\r\n  Original  '
        record = {'id':'safe', 'payload':{'role':'composer','name':'Tertuliano Santos','text':exact,'approved':True}}
        proposal = {'identity':{'composer':'Tertuliano Santos'}, 'description':'SIGA A FILARMÔNICA\n\nSobre o compositor: anterior\n\nRetreta\nhttps://youtube.com/playlist?list=original'}
        result = enrich_proposal(proposal, [record])
        self.assertEqual(result['description'], 'SIGA A FILARMÔNICA\n\n' + exact + '\n\nRetreta\nhttps://youtube.com/playlist?list=original')
        self.assertEqual(enrich_proposal(dict(proposal, identity={'composer':'Outro'}), [record]), dict(proposal,identity={'composer':'Outro'}))


if __name__ == '__main__':
    unittest.main()
