"""Simulation du parcours réel du moteur, sur base temporaire uniquement."""
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from escape_engine import Engine

DATA=json.loads((ROOT/'escape_content/fractures.json').read_text(encoding='utf8'))
# Scenario: the player misses the souvenir collectibles; ordinary puzzle rewards remain intact.
for room in DATA['rooms']:
    for puzzle in room.get('puzzles', []):
        puzzle['rewards'] = [x for x in puzzle.get('rewards', []) if not x.startswith('souvenir_')]
    for hotspot in room.get('hotspots', []):
        hotspot['rewards'] = [x for x in hotspot.get('rewards', []) if not x.startswith('souvenir_')]
ROOMS={r['id']:r for r in DATA['rooms']}

def run():
    with tempfile.TemporaryDirectory(prefix='escape_test_') as td:
        engine=Engine(Path(td)/'test.sqlite')
        g,a,m,o=1,DATA['id'],'solo',123
        engine.start(g,a,m,o,DATA['rooms'][0]['id'])
        events=[]; issues=[]
        for _ in range(20):
            state=engine.status(g,a,m,o)
            if state['completed']:break
            room=ROOMS[state['room_id']]; events.append('Salle: '+room['id'])
            # Try all actions in a room until no further state changes.
            for iteration in range(35):
                before=engine.status(g,a,m,o)
                if before['room_id']!=room['id']:break
                for h in room.get('hotspots',[]):
                    engine.inspect(g,a,m,o,DATA,h['id'])
                for rec in room.get('recipes',[]):
                    engine.combine(g,a,m,o,DATA,*rec['ingredients'])
                for p in room['puzzles']:
                    if p['id'] in engine.status(g,a,m,o)['solved']:continue
                    if p.get('next_room') or p.get('finish') or p.get('finish_if_unqualified'):continue
                    access=engine.puzzle_access(g,a,m,o,DATA,p['id'])
                    if access['accessible']:
                        result=engine.answer(g,a,m,o,DATA,p['id'],p['answers'][0])
                        if not result['correct']:issues.append(f"{p['id']}: réponse rejetée: {result}")
                for h in room.get('hotspots',[]):engine.inspect(g,a,m,o,DATA,h['id'])
                for rec in room.get('recipes',[]):engine.combine(g,a,m,o,DATA,*rec['ingredients'])
                after=engine.status(g,a,m,o)
                if set(after['solved'])==set(before['solved']) and set(after['items'])==set(before['items']):break
            # exit only after non-exit puzzles
            for p in room['puzzles']:
                if not (p.get('next_room') or p.get('finish') or p.get('finish_if_unqualified')):continue
                access=engine.puzzle_access(g,a,m,o,DATA,p['id'])
                if not access['accessible']:
                    issues.append(f"BLOQUÉ {room['id']}/{p['id']}: {access['reason']}; items={engine.status(g,a,m,o)['items']}")
                    continue
                result=engine.answer(g,a,m,o,DATA,p['id'],p['answers'][0]);events.append(f"Sortie {room['id']}: {result}")
            after=engine.status(g,a,m,o)
            if after['room_id']==room['id'] and not after['completed']:
                issues.append(f"Aucune transition depuis {room['id']}");break
        final=engine.status(g,a,m,o)
        print('\n'.join(events));print('FINAL',final['room_id'],final['completed'],'solved',len(final['solved']),'items',len(final['items']))
        print('ISSUES',len(issues));print('\n'.join(issues))
        assert not issues and final['completed'] and final['room_id']=='tribunal', (issues, final)
if __name__=='__main__':run()
