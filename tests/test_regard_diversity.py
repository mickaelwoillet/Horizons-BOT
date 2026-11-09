import unittest
from cogs.regard_editorial import editorial_duplicate, editorial_subject, article_card

class RegardDiversity(unittest.TestCase):
    def test_same_person_different_story(self):
        self.assertTrue(editorial_duplicate('Marine Le Pen condamnée dans une affaire judiciaire - Le Monde', 'Nouvelle audience pour Marine Le Pen - Ouest-France'))
        self.assertTrue(editorial_duplicate('Éric Zemmour et la justice - L’Humanité', 'Manifestation après des propos de Zemmour - Ouest-France'))
    def test_distinct_topics(self):
        self.assertFalse(editorial_duplicate('Marine Le Pen devant la justice', 'Une association soutient les victimes de transphobie'))
if __name__=='__main__':unittest.main()
