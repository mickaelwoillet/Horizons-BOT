"""Promenades scénarisées cohérentes avec leurs sept décors (V2.2)."""
from __future__ import annotations

# Chaque étape et ses choix se rapportent exclusivement aux éléments visibles du décor.
WALKS = {
 'prairie': ('🌅 Prairie enchantée', (
  ('Au milieu de la prairie, NOX admire les lumières du soir. Où aller ?', ('Vers les fleurs', 'Suivre la brise', 'Observer le ciel')),
  ('Une lumière traverse les herbes. Comment réagir ?', ('La regarder', 'Imaginer une histoire', 'S’asseoir ensemble')),
  ('Le soleil décline sur les collines. Que faire ?', ('Profiter du calme', 'Chercher un souvenir', 'Rentrer doucement'))),
  ('Le souffle de la prairie','Le rayon du soir','La lumière dans l’herbe')),
 'etoiles': ('🌌 Vallée des étoiles', (
  ('Le ciel de la vallée brille de mille étoiles. Que montre-t-on à NOX ?', ('Une constellation', 'La lune', 'Une étoile filante')),
  ('Une lueur mystérieuse scintille au loin. Que faire ?', ('L’observer', 'Faire un vœu', 'Compter les étoiles')),
  ('La nuit s’apaise dans la vallée. Comment finir ?', ('Raconter une légende', 'Écouter le silence', 'Rentrer ensemble'))),
  ('La constellation secrète','Le vœu des étoiles','La lueur de la vallée')),
 'plage': ('🏖️ Plage des coquillages', (
  ('Les vagues effleurent les coquillages. Que choisit NOX ?', ('Ramasser un coquillage', 'Suivre le rivage', 'Regarder les vagues')),
  ('Le soleil fait scintiller l’eau turquoise. Que faire ?', ('Dessiner dans le sable', 'Observer les reflets', 'Chercher une empreinte')),
  ('La mer devient paisible. Quel souvenir garder ?', ('Le chant des vagues', 'Une forme de coquillage', 'Un dessin dans le sable'))),
  ('Le coquillage chantant','Le dessin des marées','La chanson des vagues')),
 'jardin': ('🌸 Jardin des souhaits', (
  ('Au jardin, une arche fleurie mène vers un bassin. Où aller ?', ('Vers l’arche', 'Au bord du bassin', 'Sous les fleurs')),
  ('Des pétales dansent autour de NOX. Que faire ?', ('Les observer', 'Inventer un vœu', 'Écouter la cascade')),
  ('Le jardin s’illumine doucement. Comment finir ?', ('Admirer les fleurs', 'Faire une pause', 'Rentrer par le sentier'))),
  ('Le pétale porte-bonheur','Le reflet du bassin','Le souhait secret')),
 'foret': ('🍄 Forêt des lucioles', (
  ('Un sentier traverse les champignons lumineux. Où aller ?', ('Suivre le sentier', 'Voir les champignons', 'Écouter la cascade')),
  ('Des lucioles scintillent près des arbres. Que propose NOX ?', ('Les observer', 'Leur inventer des noms', 'Chercher leur lumière')),
  ('Le sous-bois devient silencieux. Comment finir ?', ('Faire une pause', 'Regarder les étoiles', 'Revenir sur le chemin'))),
  ('La luciole curieuse','Le champignon étoilé','Le secret du sentier')),
 'automne': ('🍁 Forêt d’automne', (
  ('Les feuilles rouges bordent le pont de pierre. Où aller ?', ('Traverser le pont', 'Longer la rivière', 'Admirer les feuilles')),
  ('La cascade résonne près du chalet. Que fait NOX ?', ('Écouter l’eau', 'Observer les lanternes', 'Regarder le chalet')),
  ('Le soleil descend sur les arbres dorés. Comment finir ?', ('Garder une jolie feuille', 'S’asseoir près du pont', 'Rentrer par le sentier'))),
  ('La feuille flamboyante','Le murmure de la cascade','Le pont des lanternes')),
 'hiver': ('❄️ Lac des aurores', (
  ('Des aurores illuminent le lac enneigé. Où regarder ?', ('Vers les aurores', 'Vers le chalet', 'Vers les montagnes')),
  ('Des lanternes éclairent la neige au bord du lac. Que faire ?', ('Suivre les traces', 'Observer les reflets', 'Admirer les sapins')),
  ('La nuit devient froide et paisible. Comment terminer ?', ('Rentrer au chaud', 'Faire un dernier vœu', 'Saluer le lac'))),
  ('Le reflet des aurores','La lumière du chalet','Les traces dans la neige')),
}

# Image 16:9 paysage par promenade, conservée dans le ZIP.
SCENE_IMAGES = {code: f'assets/nox_junior/walks/{code}.webp' for code in WALKS}

def start(code):
    if code not in WALKS: raise ValueError('Promenade inconnue.')
    return {'code':code,'step':0,'text':WALKS[code][1][0][0], 'path':[], 'done':False}

def choices(session):
    if session['done']: return ()
    return WALKS[session['code']][1][session['step']][1]

def advance(session, choice):
    if session['done']: raise ValueError('Promenade terminée.')
    options=choices(session)
    if not isinstance(choice,int) or choice<0 or choice>=len(options): raise ValueError('Choix invalide.')
    path=session['path']+[choice]
    step=session['step']+1
    done=step==len(WALKS[session['code']][1])
    if done:
        keeps=WALKS[session['code']][2]
        souvenir=keeps[(sum(path)+len(path))%len(keeps)]
        return {'code':session['code'],'step':step,'path':path,'done':True,'text':f'NOX rentre heureux de votre promenade. Souvenir : {souvenir}.','souvenir':souvenir}
    return {'code':session['code'],'step':step,'path':path,'done':False,'text':WALKS[session['code']][1][step][0]}
