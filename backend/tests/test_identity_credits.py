import unittest
from app.services.description_service import identity

class IdentityCreditTests(unittest.TestCase):
    def test_portuguese_name_particles_and_long_credit(self):
        for name in ('João da Justa', 'Mamede do Rosário', 'A. M. do Espírito Santo'):
            video={'snippet':{'title':f'Dobrado Allah — {name} — Sociedade Filarmônica União Sanfelixta'}}
            self.assertEqual(identity(video)['composer'],name)

    def test_arranger_never_becomes_composer_and_event_is_not_author(self):
        item=identity({'snippet':{'title':'Foi Assim — Arr. Antônio Neves — Sociedade Filarmônica União Sanfelixta'}})
        self.assertEqual(item['composer'],'')
        self.assertEqual(item['arranger'],'Antônio Neves')
        self.assertEqual(identity({'snippet':{'title':'Allah — Primeira Noite — Sociedade Filarmônica União Sanfelixta'}})['composer'],'')
