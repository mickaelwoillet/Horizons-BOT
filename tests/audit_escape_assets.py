"""Audit non-divulgâchant des ressources visuelles Escape Game HORIZONS."""
from pathlib import Path
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'escape_content'

def audit():
    catalog = json.loads((CONTENT / 'fractures.json').read_text(encoding='utf-8'))
    results = []
    for index, room in enumerate(catalog['rooms'], 1):
        name = room.get('image_file')
        image = CONTENT / 'images' / name if isinstance(name, str) and name else None
        entry = {'room': index, 'image_defined': bool(name), 'image_exists': bool(image and image.is_file()), 'image_valid': False, 'size': None}
        if entry['image_exists']:
            try:
                with Image.open(image) as im:
                    im.verify()
                with Image.open(image) as im:
                    entry['size'] = list(im.size)
                    entry['image_valid'] = im.width >= 1200 and im.height >= 675
            except (OSError, ValueError):
                pass
        results.append(entry)
    return results

if __name__ == '__main__':
    results = audit()
    print(f"Salles: {len(results)} | images présentes et valides: {sum(r['image_valid'] for r in results)}")
    for r in results:
        if not r['image_valid']:
            print(f"Ressource manquante/invalide : salle {r['room']:02d}")
