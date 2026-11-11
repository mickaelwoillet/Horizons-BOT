import tempfile
import unittest
from pathlib import Path
from PIL import Image
from cogs import nox_junior_engine as engine
from cogs import nox_junior_visual as visual

class TestRainbowV10(unittest.TestCase):
    def test_color_available_for_adoption(self):
        self.assertEqual(len(engine.COLORS), 9)
        self.assertIn('arc_en_ciel', engine.COLORS)
        with tempfile.TemporaryDirectory() as d:
            with engine.connect(Path(d) / 'junior.sqlite3') as con:
                pet_id=engine.adopt(con,1,42,'Prisme','arc_en_ciel',True)
                row=engine.snapshot(con,pet_id,42,1)
                self.assertEqual(row['color'],'arc_en_ciel')

    def test_all_growth_stages_and_moods(self):
        for stage in visual.STAGES:
            for mood in visual.MOODS:
                result=visual.render({'id':99,'color':'arc_en_ciel'},stage=stage,mood=mood)
                im=Image.open(result)
                self.assertEqual(im.format,'PNG')
                self.assertEqual(im.size,(760,440))

    def test_rainbow_stripes_are_visibly_multicolored(self):
        for stage in ('oeuf','bebe','adulte'):
            im=Image.open(visual.render({'id':4,'color':'arc_en_ciel'},stage=stage))
            # Multiple distinct bright stripe colors, rather than one solid purple fill.
            pixels=[im.getpixel((380,y)) for y in range(125,350,5)]
            self.assertGreater(len(set(pixels)),4)

    def test_existing_colors_unchanged(self):
        self.assertEqual(len(visual.PALETTE),9)
        self.assertEqual(visual.PALETTE['bleu'],(63,155,242))
        self.assertEqual(visual.render({'id':3,'color':'bleu'}).getvalue(),visual.render({'id':3,'color':'bleu'}).getvalue())
