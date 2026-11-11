"""NOX Junior: repeatable, reward-free companion activities.

No economy, care counters, timers or database writes are performed here.
All stories are short branching conversations and may be replayed.
"""
from __future__ import annotations
import random

ACTIVITIES = {
    'parler': {
        'title': '💬 Discuter avec NOX',
        'intro': 'NOX vient se blottir près de toi. De quoi veux-tu parler ?',
        'steps': (
            (('Comment te sens-tu ?', 'À quoi rêves-tu ?', 'Une petite bêtise ?'),
             ('NOX penche la tête et te raconte sa journée.', 'NOX ferme les yeux et imagine un ciel plein de comètes.', 'NOX glousse : il a caché une étoile sous son coussin !')),
            (('Je t’écoute 💜', 'Et ensuite ?', 'On invente la suite !'),
             ('NOX est ravi que tu lui consacres du temps.', 'Il ajoute un détail absolument farfelu à son récit.', 'Vous inventez ensemble une nouvelle constellation.')),
            (('Un câlin virtuel', 'On recommencera !'),
             ('NOX te répond par un petit ronronnement cosmique.', 'NOX promet de garder une autre histoire pour la prochaine fois.')),
        ),
    },
    'histoires': {
        'title': '📖 Histoires à deux',
        'intro': 'Une histoire commence : une étoile a perdu son chemin. Où part-elle ?',
        'steps': (
            (('Vers la lune', 'Dans un jardin lumineux', 'Sur un nuage'),
             ('La lune lui offre une carte scintillante.', 'Les lucioles lui montrent un sentier secret.', 'Un nuage moelleux lui propose de voyager.')),
            (('Suivre une lumière', 'Demander de l’aide', 'Faire une pause'),
             ('Un petit phare céleste s’allume au loin.', 'Une comète amicale vient à votre rencontre.', 'Vous admirez le ciel et retrouvez votre courage.')),
            (('Rentrer ensemble', 'Offrir un souvenir'),
             ('L’étoile retrouve sa place et NOX applaudit la fin.', 'L’étoile vous offre un sourire avant de repartir.')),
        ),
    },
    'jouets': {
        'title': '🧸 Jouets interactifs',
        'intro': 'NOX ouvre son coffre imaginaire. Avec quoi voulez-vous jouer ?',
        'steps': (
            (('Balle lunaire', 'Bulles cosmiques', 'Plume magique'),
             ('La balle rebondit et NOX court après en riant.', 'NOX essaie d’attraper une bulle avec le museau.', 'La plume chatouille doucement les oreilles de NOX.')),
            (('Encore un tour !', 'Changer de rythme', 'Inventer une règle'),
             ('NOX tente une figure spectaculaire… presque réussie !', 'Vous ralentissez et profitez du jeu ensemble.', 'NOX invente une règle qui le fait gagner à chaque fois.')),
            (('Ranger ensemble', 'Féliciter NOX'),
             ('NOX range les jouets avec une fierté visible.', 'NOX bombe le torse et te remercie de jouer avec lui.')),
        ),
    },
    'calme': {
        'title': '🌙 Moments calmes',
        'intro': 'NOX profite d’un instant tranquille. Que souhaites-tu partager ?',
        'steps': (
            (('Observer les étoiles', 'Écouter le silence', 'Imaginer un rêve'),
             ('Une constellation semble dessiner une petite patte.', 'NOX respire doucement et profite de ta présence.', 'Vous imaginez une île où les nuages sont des coussins.')),
            (('Rester un peu', 'Décrire une étoile', 'Souhaiter bonne nuit'),
             ('NOX se sent bien à tes côtés.', 'NOX choisit une étoile et lui donne un nom amusant.', 'NOX ferme les yeux quelques instants, rassuré.')),
            (('Terminer doucement', 'Garder ce moment en mémoire'),
             ('Vous terminez ce moment dans le calme.', 'Ce petit instant restera une jolie histoire à raconter.')),
        ),
    },
}


def start(activity):
    if activity not in ACTIVITIES:
        raise ValueError('Activité inconnue.')
    return {'activity': activity, 'step': 0, 'text': ACTIVITIES[activity]['intro'], 'done': False}


def choices(session):
    if session['done']:
        return ()
    return ACTIVITIES[session['activity']]['steps'][session['step']][0]


def advance(session, choice_index):
    if session['done']:
        raise ValueError('Cette activité est terminée.')
    options, outcomes = ACTIVITIES[session['activity']]['steps'][session['step']]
    if not isinstance(choice_index, int) or not 0 <= choice_index < len(options):
        raise ValueError('Choix invalide.')
    next_step = session['step'] + 1
    return {'activity': session['activity'], 'step': next_step,
            'text': outcomes[choice_index],
            'done': next_step >= len(ACTIVITIES[session['activity']]['steps'])}
