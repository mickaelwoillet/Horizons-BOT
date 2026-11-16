"""Audit non-spoiler des ressources et des ancrages visuels de l'Escape Game.

Ne certifie jamais qu'un détail est visible sans validation explicite.
"""
import json
from pathlib import Path
from audit_escape_assets import audit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'escape_content' / 'fractures.json'


def run():
    rooms = json.loads(CATALOG.read_text(encoding='utf-8'))['rooms']
    images = audit()
    findings = []
    for i, room in enumerate(rooms, 1):
        asset = images[i - 1] if i <= len(images) else {'image_valid': False}
        hotspots = room.get('hotspots', [])
        missing_anchors = [h.get('id', f'interaction_{n}') for n, h in enumerate(hotspots, 1)
                           if not str(h.get('visual_anchor') or '').strip()]
        invalid_anchors = [h.get('id', f'interaction_{n}') for n, h in enumerate(hotspots, 1)
                           if h.get('visual_verified') is True and not str(h.get('visual_anchor') or '').strip()]
        findings.append({
            'room_number': i,
            'asset_valid': bool(asset.get('image_valid')),
            'puzzle_count': len(room.get('puzzles', [])),
            'interactive_elements': len(hotspots),
            'no_interactive_elements': not bool(hotspots),
            'missing_visual_anchors': missing_anchors,
            'invalid_visual_certifications': invalid_anchors,
            'visual_anchor_documented': not missing_anchors,
            'visual_match_verified': bool(asset.get('image_valid')) and all(
                h.get('visual_verified') is True and str(h.get('visual_anchor') or '').strip()
                for h in hotspots
            ) and bool(hotspots),
        })
    return findings


def summary(rows):
    return {
        'rooms': len(rows),
        'valid_images': sum(r['asset_valid'] for r in rows),
        'hotspots_missing_anchors': sum(len(r['missing_visual_anchors']) for r in rows),
        'rooms_visually_certified': sum(r['visual_match_verified'] for r in rows),
        'invalid_certifications': sum(len(r['invalid_visual_certifications']) for r in rows),
        'rooms_without_hotspots': sum(r['no_interactive_elements'] for r in rows),
        'rooms_with_hotspots': sum(not r['no_interactive_elements'] for r in rows),
    }


if __name__ == '__main__':
    print(json.dumps(summary(run()), ensure_ascii=False, indent=2))
