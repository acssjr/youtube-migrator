import unittest
from types import SimpleNamespace
from app.api.acervo_search import build_catalog, matches_filters


class SearchTests(unittest.TestCase):
    def video(self, id='abcdefghijk', composer='João Santos'):
        return {'id': id, 'snippet': {'channelId': 'channel', 'title': f'Dobrado Allah — {composer} — Sociedade Filarmônica União Sanfelixta', 'description': 'Texto exato.', 'publishedAt': '2026-09-29T10:00:00Z'}}

    def test_combined_accent_insensitive_filters_and_event_date(self):
        event = SimpleNamespace(kind='event', payload={'name': 'Retreta — 5ª Noite', 'project': 'Retreta', 'performed_at': '2023-09-01', 'ensemble': 'União Sanfelixta', 'video_ids': ['abcdefghijk']})
        row = build_catalog([self.video()], [event], 'channel')[0]
        self.assertTrue(matches_filters(row, composer='joao', ensemble='uniao', genre='dobrado', project='retreta', date_from='2023-01-01', date_to='2023-12-31', date_basis='performed'))
        self.assertFalse(matches_filters(row, composer='Outro'))
        self.assertFalse(matches_filters(row, date_from='2026-01-01', date_basis='performed'))
        self.assertTrue(matches_filters(row, date_from='2026-01-01'))
        self.assertEqual(row['description'], 'Texto exato.')

    def test_no_guessed_event_date_or_cross_composer_join(self):
        work = SimpleNamespace(kind='work', payload={'name': 'Allah', 'composer': 'Outra Pessoa', 'genre': 'Marcha'})
        row = build_catalog([self.video()], [work], 'channel')[0]
        self.assertEqual(row['identity_source'], 'title')
        self.assertEqual(row['composer'], 'João Santos')
        self.assertFalse(matches_filters(row, date_from='2000-01-01', date_basis='performed'))
        self.assertEqual(build_catalog([self.video()], [], 'other'), [])

    def test_saved_source_and_ambiguous_records(self):
        work = SimpleNamespace(kind='work', payload={'name': 'Nome revisado', 'composer': 'Nome correto', 'sources': [{'video_id': 'abcdefghijk'}]})
        row = build_catalog([self.video()], [work], 'channel')[0]
        self.assertEqual(row['work'], 'Nome revisado')
        self.assertEqual(row['identity_source'], 'catalog')
        row = build_catalog([self.video()], [work, work], 'channel')[0]
        self.assertTrue(row['catalog_ambiguous'])
        self.assertEqual(row['identity_source'], 'title')
    def test_work_alias_still_requires_composer_and_arranger(self):
        work = SimpleNamespace(kind='work', payload={'name':'Nome canônico','aliases':'Allah; Outra grafia','composer':'João Santos','arranger':''})
        row=build_catalog([self.video()], [work], 'channel')[0]
        self.assertEqual(row['work'],'Nome canônico')
        self.assertEqual(build_catalog([self.video(composer='Outro')],[work],'channel')[0]['identity_source'],'title')
