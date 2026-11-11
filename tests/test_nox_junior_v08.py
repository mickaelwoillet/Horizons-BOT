import io
import unittest
from PIL import Image
from cogs import nox_junior_visual as visual

class TestVisual(unittest.TestCase):
    def test_every_color_stage(self):
        for color in visual.PALETTE:
            for stage in visual.STAGES:
                img=Image.open(visual.render({'id':12,'color':color},stage=stage))
                self.assertEqual(img.size,(760,440))
    def test_every_mood_theme(self):
        for mood in visual.MOODS:
            for theme in visual.THEMES:
                self.assertEqual(Image.open(visual.render({'id':3,'color':'bleu'},mood=mood,theme=theme)).format,'PNG')
    def test_determinism(self):
        p={'id':7,'color':'violet'}
        self.assertEqual(visual.render(p).getvalue(),visual.render(p).getvalue())
    def test_distinct(self):
        p={'id':7,'color':'violet'}
        self.assertNotEqual(visual.render(p,stage='oeuf').getvalue(),visual.render(p,stage='adulte').getvalue())
        self.assertNotEqual(visual.render(p,theme='cosmos').getvalue(),visual.render(p,theme='foret').getvalue())
    def test_validation(self):
        with self.assertRaises(ValueError): visual.render({'id':1,'color':'unknown'})
        with self.assertRaises(ValueError): visual.render({'id':1,'color':'bleu'},stage='unknown')
