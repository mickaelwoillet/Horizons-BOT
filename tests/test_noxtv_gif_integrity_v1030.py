"""Checks actual GIF media, not merely filename extensions."""
import json
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'data' / 'nox_tv'


def test_gifs_have_multiple_frames_and_real_motion():
    entries = json.loads((MEDIA / 'catalogue.json').read_text(encoding='utf8'))
    gifs = [e for e in entries if e['file'].lower().endswith('.gif')]
    assert len(gifs) >= 4
    for entry in gifs:
        with Image.open(MEDIA / entry['file']) as img:
            assert img.format == 'GIF'
            assert img.n_frames >= 3, entry['id']
            img.seek(0)
            first = img.convert('RGB').resize((96, 72))
            changes = 0
            for k in range(1, img.n_frames):
                img.seek(k)
                current = img.convert('RGB').resize((96, 72))
                if ImageChops.difference(first, current).getbbox():
                    changes += 1
            assert changes >= 2, entry['id']


def test_gifs_have_distinct_content():
    entries = json.loads((MEDIA / 'catalogue.json').read_text(encoding='utf8'))
    fingerprints = []
    for entry in entries:
        if not entry['file'].lower().endswith('.gif'):
            continue
        with Image.open(MEDIA / entry['file']) as img:
            img.seek(img.n_frames // 2)
            pixels = img.convert('L').resize((16, 16)).tobytes()
            fingerprints.append((entry['id'], pixels))
    for i, (name, pixels) in enumerate(fingerprints):
        for other, second in fingerprints[i + 1:]:
            assert pixels != second, (name, other)
