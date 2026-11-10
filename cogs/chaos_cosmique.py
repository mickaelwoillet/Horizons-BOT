"""HORIZONS V9.0 — Chaos Cosmique, univers narratif autonome et optionnel."""
from __future__ import annotations

import asyncio
import logging
import random
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR, LOCAL_TIMEZONE, GUILD_ID
from .embed_theme import horizons_embed

log = logging.getLogger(__name__)
DB_PATH = DATA_DIR / 'chaos_cosmique.sqlite3'

EVENTS = (
    ('porte', '🚪 La Porte du 13e Mardi', 'Une porte frappe trois coups de l’intérieur. Elle recherche ses chaussettes.',
     ('Ouvrir la porte', 'Observer prudemment', 'Envoyer Nox'),
     (('Un bureau de poste intergalactique réclame trois millions de poussières d’étoiles.', 12, 8, -3),
      ('La porte avoue être une fenêtre timide. Elle livre un fragment de carte.', -3, 5, 7),
      ('Nox revient avec une cuillère dorée et un diplôme de plomberie cosmique.', 7, 4, 2))),
    ('canard', '🦆 Le Canard Suprême', 'Un canard couronné revendique la propriété de l’Observatoire.',
     ('Négocier', 'Organiser un procès', 'Lui offrir du pain stellaire'),
     (('Le canard exige un ministère des flaques. Les négociations continuent.', 4, 3, 5),
      ('Le tribunal statue : le canard doit payer son loyer en compliments.', -2, 6, 7),
      ('Le canard devient ambassadeur des miettes interstellaires.', -5, 7, 8))),
    ('horloge', '⏰ La Grève du Temps', 'Toutes les horloges affichent 25h61. Le mardi refuse de se terminer.',
     ('Réparer les aiguilles', 'Écouter le temps', 'Demander à Nox'),
     (('Les aiguilles reprennent leur service, mais demandent des congés.', -4, 7, 4),
      ('Le temps révèle un secret : les minutes aiment les histoires.', -2, 5, 8),
      ('Nox invente le mercredi et demi. Le calendrier proteste.', 9, 6, -2))),
    ('jardin', '🌱 Le Jardin des Étoiles Perdues', 'Une plante lumineuse pousse dans une tasse abandonnée.',
     ('L’arroser', 'Lui raconter une histoire', 'Laisser Nox la nommer'),
     (('La plante offre une étoile de papier et remercie avec élégance.', -3, 6, 8),
      ('La plante fleurit en petites bibliothèques. Le silence applaudit.', -4, 5, 9),
      ('Nox l’appelle Gérard. Gérard devient immédiatement célèbre.', 5, 7, 4))),
)

EVENTS = EVENTS + (
('chaussette', '🧦 La Conspiration des Chaussettes', 'Toutes les chaussettes de l’Observatoire ont demandé l’asile politique.', ('Ouvrir une ambassade', 'Mener l’enquête', 'Consulter Nox'), (('Une ambassade ouvre dans un tiroir. Son hymne est un bruit de machine à laver.', 3, 5, 5), ('Les chaussettes se cachent dans la quatrième dimension des placards.', -2, 6, 4), ('Nox propose une monarchie des pantoufles. Personne ne l’a élu.', 7, 4, 2))),
('lune', '🌙 La Lune a posé un RTT', 'La Lune annonce qu’elle ne brillera pas ce soir. Elle est fatiguée.', ('Lui offrir une veilleuse', 'Respecter son repos', 'Lui écrire un poème'), (('La Lune accepte une lampe de poche et des congés payés.', -2, 4, 6), ('Les étoiles organisent une garde de nuit solidaire.', -4, 3, 9), ('La Lune rougit. Un astronome dépose une plainte pour excès de tendresse.', 2, 6, 7))),
('miroir', '🪞 Le Miroir qui prédit hier', 'Un miroir affirme connaître l’avenir, mais uniquement celui de la veille.', ('L’interroger', 'Le retourner', 'Le laisser rêver'), (('Le miroir annonce une grande révélation : hier était lundi.', 4, 4, 2), ('Derrière lui, une constellation joue au cache-cache.', -2, 7, 5), ('Le miroir invente un souvenir qui fait sourire Nox.', -3, 4, 8))),
('ascenseur', '🛗 Ascenseur pour nulle part', 'Un ascenseur apparaît au milieu du jardin, sans étage ni bouton.', ('Monter dedans', 'Lui demander sa destination', 'Le décorer'), (('L’ascenseur mène à un salon de thé pour comètes.', 6, 7, 1), ('Il répond : « Je cherche encore ma vocation. »', -2, 6, 5), ('Il devient le premier musée des ascenseurs immobiles.', -3, 4, 7))),
('nuage', '☁️ Le Nuage administratif', 'Un nuage exige un formulaire pour chaque goutte de pluie.', ('Créer un guichet', 'Organiser une grève', 'Appeler Nox'), (('Les gouttes prennent un ticket. Il pleuvra dans 47 ans.', 6, 4, 0), ('Les nuages chantent sous la pluie qu’ils refusent de produire.', 3, 5, 6), ('Nox tamponne « APPROUVÉ » sur un arc-en-ciel.', -2, 6, 7))),
('constellation', '✨ La Constellation disparue', 'Une constellation manque à l’appel. Elle aurait changé de métier.', ('La rechercher', 'Publier une annonce', 'Lui souhaiter bonne chance'), (('Elle travaille désormais dans un planétarium miniature.', -2, 8, 4), ('Une étoile répond : « Elle est partie ouvrir une boulangerie. »', 3, 6, 5), ('La constellation revient offrir des croissants cosmiques.', -4, 5, 8))),
('bibliothecaire', '📚 Le Livre qui veut être lu', 'Un livre réclame un lecteur, mais critique chaque voix.', ('Lui faire la lecture', 'Le laisser lire Nox', 'Lui offrir un marque-page'), (('Le livre applaudit puis demande un rappel.', -2, 6, 8), ('Nox invente trois mots. Le dictionnaire démissionne.', 7, 7, 2), ('Le marque-page devient maire d’une petite planète.', 4, 5, 6))),
('gravite', '🪐 La Gravité en congé', 'Les objets flottent à 12 centimètres du sol. La gravité est en pause.', ('Négocier', 'Profiter du vol', 'Installer des coussins'), (('La gravité accepte de revenir après une pause café.', -5, 5, 6), ('Nox devient champion de natation dans l’air.', 8, 7, 1), ('Les coussins flottent aussi. C’était prévisible.', 3, 4, 7))),
('parapluie', '☂️ Le Parapluie philosophe', 'Un parapluie refuse de s’ouvrir tant qu’on n’a pas défini le bonheur.', ('Débattre', 'Lui raconter une blague', 'Attendre le soleil'), (('Le parapluie conclut que le bonheur est une pluie de confettis.', -2, 5, 8), ('Il rit si fort qu’il se retourne comme une crêpe.', 5, 6, 5), ('Le soleil arrive et lui propose une reconversion en parasol.', -3, 4, 7))),
('train', '🚂 Le Train des Possibles', 'Un train arrive sans rails et vend des billets pour des souvenirs futurs.', ('Acheter un billet', 'Interroger le contrôleur', 'Faire monter Nox'), (('Tu reçois un billet pour un mercredi qui n’existe pas.', 4, 8, 3), ('Le contrôleur est un hibou diplômé en imprévus.', -2, 6, 6), ('Nox devient chef de gare pendant exactement neuf secondes.', 6, 7, 4))),
('fromage', '🧀 L’Affaire du Fromage Cosmique', 'Un fromage flotte dans le ciel. Il prétend être une planète.', ('Le cartographier', 'Le goûter', 'Lui donner un nom'), (('Les astronomes découvrent une lune de camembert.', 3, 7, 4), ('Le fromage a un goût de poussière d’étoiles et de regrets.', 5, 4, 2), ('La planète Gérard II entre officiellement dans l’atlas.', -2, 5, 7))),
('radio', '📻 La Radio des Étoiles', 'Une radio diffuse des messages de demain, mais avec une voix de canard.', ('Écouter', 'Répondre', 'Changer de fréquence'), (('La radio annonce que Nox perdra une chaussette demain.', 2, 6, 5), ('Une voix remercie : « Votre appel est très important pour l’univers. »', 4, 5, 6), ('Une chanson inconnue fait danser les poussières stellaires.', -4, 7, 8)))
)
EVENT_BY_KEY = {event[0]: event for event in EVENTS}


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('''CREATE TABLE IF NOT EXISTS cosmic_world (
        guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL DEFAULT 0,
        paused INTEGER NOT NULL DEFAULT 1, energy INTEGER NOT NULL DEFAULT 50,
        chaos INTEGER NOT NULL DEFAULT 25, harmony INTEGER NOT NULL DEFAULT 50,
        last_tick TEXT NOT NULL DEFAULT '', last_event_day TEXT NOT NULL DEFAULT '',
        active_event_id INTEGER NOT NULL DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS cosmic_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
        day TEXT NOT NULL, event_key TEXT NOT NULL, message_id INTEGER NOT NULL DEFAULT 0,
        choice INTEGER, resolved_by INTEGER, resolved_at TEXT,
        UNIQUE(guild_id, day))''')
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_creature (
      guild_id INTEGER PRIMARY KEY, name TEXT NOT NULL DEFAULT 'Nox', stage INTEGER NOT NULL DEFAULT 1,
      curiosity INTEGER NOT NULL DEFAULT 50, affection INTEGER NOT NULL DEFAULT 50,
      vitality INTEGER NOT NULL DEFAULT 65, stability INTEGER NOT NULL DEFAULT 55,
      temperament TEXT NOT NULL DEFAULT 'curieux', xp INTEGER NOT NULL DEFAULT 0,
      last_care TEXT NOT NULL DEFAULT '', last_evolution TEXT NOT NULL DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_locations (
      guild_id INTEGER NOT NULL, place TEXT NOT NULL, discovered_at TEXT NOT NULL,
      PRIMARY KEY(guild_id, place))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_inventory (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item TEXT NOT NULL,
      quantity INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,user_id,item))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_actions (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, action TEXT NOT NULL,
      day TEXT NOT NULL, PRIMARY KEY(guild_id,user_id,action,day))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_chapters (
      guild_id INTEGER NOT NULL, chapter INTEGER NOT NULL, unlocked_at TEXT NOT NULL,
      PRIMARY KEY(guild_id,chapter))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_journal (
      id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, at TEXT NOT NULL,
      entry TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_panels (
      guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL)""")
    # V10.1 : progression optionnelle, sans migration destructive.
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_missions (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL,
      mission TEXT NOT NULL, claimed_at TEXT,
      PRIMARY KEY(guild_id,user_id,day))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_bonds (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, character TEXT NOT NULL,
      affinity INTEGER NOT NULL DEFAULT 0, last_meeting TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(guild_id,user_id,character))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_secrets (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, secret TEXT NOT NULL,
      discovered_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id,secret))""")
    # V10.2 : progression collective et saison narrative, sans altérer les données existantes.
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_expeditions (
      guild_id INTEGER NOT NULL, season INTEGER NOT NULL, contributions INTEGER NOT NULL DEFAULT 0,
      completed_at TEXT, PRIMARY KEY(guild_id,season))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_expedition_actions (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL,
      season INTEGER NOT NULL, PRIMARY KEY(guild_id,user_id,day,season))""")
    # V10.3 : choix narratifs personnels, persistants et sans réinitialisation des autres données.
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_paradox_choices (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL,
      scene_key TEXT NOT NULL, choice INTEGER NOT NULL, result TEXT NOT NULL,
      PRIMARY KEY(guild_id,user_id,day))""")
    # V10.4 : intrigues croisées, choix uniques et conséquences persistantes.
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_crossroads (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL,
      arc_key TEXT NOT NULL, choice INTEGER NOT NULL, outcome TEXT NOT NULL,
      PRIMARY KEY(guild_id,user_id,day))""")
    # V10.5 : échos narratifs différés, indépendants des anciennes tables.
    conn.execute("""CREATE TABLE IF NOT EXISTS cosmic_echoes (
      guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, source_day TEXT NOT NULL,
      due_day TEXT NOT NULL, arc_key TEXT NOT NULL, choice INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', result TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(guild_id,user_id,source_day))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cosmic_echo_due ON cosmic_echoes(guild_id,status,due_day)")
    conn.commit()
    return conn


def ensure_world(conn, guild_id):
    conn.execute('INSERT OR IGNORE INTO cosmic_world(guild_id) VALUES (?)', (guild_id,))
    return conn.execute('SELECT * FROM cosmic_world WHERE guild_id=?', (guild_id,)).fetchone()


def clamp(value):
    return max(0, min(100, int(value)))


def tick_world(conn, guild_id, day):
    """Une seule évolution passive par date locale, même après redémarrage."""
    world = ensure_world(conn, guild_id)
    if world['last_tick'] == day or world['paused']:
        return world
    conn.execute('''UPDATE cosmic_world SET last_tick=?,
        energy=MIN(100, energy+2), chaos=MAX(0, chaos-1),
        harmony=MIN(100, harmony+1) WHERE guild_id=?''', (day, guild_id))
    return ensure_world(conn, guild_id)


def world_embed(world):
    embed = horizons_embed(title='🌌 Observatoire — Chaos Cosmique', color=0x5876E8,
        description=('Un univers fictif qui évolue au rythme des découvertes.\n'
                     '🔭 **Lieu découvert :** L’Observatoire\n'
                     '👾 **Nox :** une présence curieuse rôde dans les couloirs…'))
    embed.add_field(name='✨ Énergie', value=f"{world['energy']}/100")
    embed.add_field(name='🌀 Chaos', value=f"{world['chaos']}/100")
    embed.add_field(name='💙 Harmonie', value=f"{world['harmony']}/100")
    embed.set_footer(text='HORIZONS V9.0 · Univers narratif fictif · Sans conséquence sur les autres jeux')
    return embed


def event_embed(event, resolved=None):
    embed = horizons_embed(title=event[1], description=event[2], color=0x8860DA)
    if resolved is not None:
        ending = event[4][resolved]
        embed.add_field(name='📜 Conséquence', value=ending[0], inline=False)
        embed.set_footer(text='Anomalie résolue · Une nouvelle histoire apparaîtra plus tard')
    else:
        embed.add_field(name='🔮 Que faire ?', value='Choisissez ensemble la suite de cette histoire.', inline=False)
        embed.set_footer(text='Le premier choix valide détermine la suite · HORIZONS V9.0')
    return embed


class CosmicChoices(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def resolve(self, interaction: discord.Interaction, choice: int):
        if not interaction.guild:
            await interaction.response.send_message('Cette aventure se joue sur le serveur.', ephemeral=True)
            return
        with connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            world = ensure_world(conn, interaction.guild.id)
            row = conn.execute('SELECT * FROM cosmic_events WHERE id=? AND guild_id=?',
                               (world['active_event_id'], interaction.guild.id)).fetchone()
            if not row or row['choice'] is not None or row['message_id'] != interaction.message.id:
                return await interaction.response.send_message('Cette anomalie est déjà terminée ou n’est plus active.', ephemeral=True)
            creature(conn, interaction.guild.id)
            event = EVENT_BY_KEY[row['event_key']]
            outcome = event[4][choice]
            conn.execute('UPDATE cosmic_events SET choice=?, resolved_by=?, resolved_at=? WHERE id=? AND choice IS NULL',
                         (choice, interaction.user.id, datetime.now(LOCAL_TIMEZONE).isoformat(), row['id']))
            conn.execute('''UPDATE cosmic_world SET chaos=?, energy=?, harmony=?, active_event_id=0 WHERE guild_id=?''',
                         (clamp(world['chaos'] + outcome[1]), clamp(world['energy'] + outcome[2]),
                          clamp(world['harmony'] + outcome[3]), interaction.guild.id))
            conn.execute('UPDATE cosmic_creature SET xp=xp+3, curiosity=MIN(100,curiosity+2) WHERE guild_id=?', (interaction.guild.id,))
            unlocks(conn, interaction.guild.id)
            journal(conn, interaction.guild.id, f'Anomalie {event[1]} résolue par {interaction.user.display_name}.')
        await interaction.response.edit_message(embed=event_embed(event, choice), view=None)

    @discord.ui.button(label='Option 1', style=discord.ButtonStyle.primary, custom_id='cosmic:v90:choice:0', emoji='🚪')
    async def option_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, 0)

    @discord.ui.button(label='Option 2', style=discord.ButtonStyle.secondary, custom_id='cosmic:v90:choice:1', emoji='🔭')
    async def option_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, 1)

    @discord.ui.button(label='Option 3', style=discord.ButtonStyle.secondary, custom_id='cosmic:v90:choice:2', emoji='👾')
    async def option_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, 2)



PLACES = {
 'observatoire': ('🔭 Observatoire', 'Le point de départ de toutes les impossibilités.', 0),
 'jardin': ('🌱 Jardin des étoiles perdues', 'Les fleurs y poussent parfois à l’envers.', 3),
 'bibliotheque': ('📚 Bibliothèque des impossibles', 'Les livres lisent les visiteurs.', 8),
 'cuisine': ('🥄 Cuisine quantique', 'Les casseroles se disputent les lois de la physique.', 15),
 'tribunal': ('🦆 Tribunal des canards', 'Toute objection doit être formulée en coin-coin.', 24),
 'neant': ('🌀 Porte du Néant', 'Une énigme dort derrière ce seuil.', 35),
}
ARTIFACTS = ('poussière d’étoile', 'biscuit lunaire', 'cuillère quantique', 'plume de comète', 'clé du mardi', 'fragment d’aurore')
CHAPTERS = (
 ('Le premier battement', 'Une nuit, l’Observatoire a respiré. Personne n’a osé lui demander pourquoi.'),
 ('La tasse oubliée', 'Une étoile minuscule s’est installée dans une tasse. Elle exige du thé et des compliments.'),
 ('La bibliothèque qui éternue', 'Un livre a éternué si fort qu’une constellation a changé de place.'),
 ('Le procès de la gravité', 'La gravité est accusée d’avoir fait tomber un gâteau. Le verdict reste suspendu.'),
 ('Le secret de Nox', 'Nox n’est pas né d’une étoile, mais d’une question que personne n’avait encore posée.'),
)

def creature(conn, guild_id):
    conn.execute('INSERT OR IGNORE INTO cosmic_creature(guild_id) VALUES (?)', (guild_id,))
    return conn.execute('SELECT * FROM cosmic_creature WHERE guild_id=?', (guild_id,)).fetchone()

def journal(conn, guild_id, entry):
    conn.execute('INSERT INTO cosmic_journal(guild_id,at,entry) VALUES(?,?,?)',
                 (guild_id, datetime.now(LOCAL_TIMEZONE).isoformat(), entry[:500]))
    conn.execute('DELETE FROM cosmic_journal WHERE guild_id=? AND id NOT IN '
                 '(SELECT id FROM cosmic_journal WHERE guild_id=? ORDER BY id DESC LIMIT 80)', (guild_id,guild_id))

def progress(conn, guild_id):
    return conn.execute('SELECT COUNT(*) AS n FROM cosmic_events WHERE guild_id=? AND choice IS NOT NULL', (guild_id,)).fetchone()['n']

def unlocks(conn, guild_id):
    n = progress(conn, guild_id)
    now = datetime.now(LOCAL_TIMEZONE).isoformat()
    found=[]
    for key, (name, _, needed) in PLACES.items():
        if n >= needed:
            cur=conn.execute('INSERT OR IGNORE INTO cosmic_locations VALUES(?,?,?)', (guild_id,key,now))
            if cur.rowcount: found.append(name)
    for i in range(min(len(CHAPTERS), 1+n//3)):
        conn.execute('INSERT OR IGNORE INTO cosmic_chapters VALUES(?,?,?)', (guild_id,i,now))
    return found

def creature_embed(c):
    stage=('🌠 Étincelle', '👾 Explorateur', '🪐 Gardien', '🌌 Légende')[min(c['stage']-1,3)]
    e=horizons_embed(title=f"👾 {c['name']} — {stage}", color=0x657CEB,
       description=f"Tempérament : **{c['temperament']}**\nUne créature imaginaire qui grandit sans jamais mourir ni punir l’absence.")
    for label,key in [('Curiosité','curiosity'),('Affection','affection'),('Vitalité','vitality'),('Stabilité','stability')]:
        e.add_field(name=label, value=f"{'▰'*(c[key]//10)}{'▱'*(10-c[key]//10)} {c[key]}/100", inline=False)
    e.set_footer(text=f"Expérience : {c['xp']} · Stade {c['stage']}/4")
    return e


# V10 INFINITY : interactions persistantes, sans commande supplémentaire par action.
NOX_LINES = {
 'parler': ['« J’ai demandé au Soleil son âge. Il m’a répondu : ça ne te regarde pas, petit astéroïde. »', '« Tu crois que les étoiles font des vœux quand elles voient passer des humains ? »', '« J’ai appris le mot diplomatie. Le canard me doit toujours un biscuit. »'],
 'nourrir': ['Nox engloutit une brioche stellaire. Une constellation demande la recette.', 'Nox goûte un biscuit lunaire et déclare officiellement la pause goûter universelle.', 'Nox mange une miette cosmique et en garde une pour demain.'],
 'jouer': ['Nox organise un cache-cache avec la gravité. La gravité triche.', 'Nox joue à saute-comète et atterrit dans une tasse de thé.', 'Nox gagne une partie d’échecs contre un caillou particulièrement mauvais joueur.'],
 'mediter': ['Nox médite en compagnie d’une comète qui ronfle.'],
 'repos': ['Nox se roule en boule et rêve d’un royaume gouverné par des coussins.', 'Nox s’endort. Ses ronflements réparent trois étoiles fatiguées.', 'Nox médite. Une chaise obtient l’illumination à sa place.'],
 'explorer': ['Nox trouve une cuillère qui se souvient du futur.', 'Nox découvre une chaussette quantique qui prétend être un ministre.', 'Nox revient avec un caillou qu’il appelle Directeur Général.'],
}
NOX_EFFECTS = {'parler':('affection',8), 'nourrir':('vitality',10), 'mediter':('stability',10), 'jouer':('curiosity',9), 'repos':('stability',10), 'explorer':('curiosity',7)}
NOX_WISHES = ('un biscuit de météorite', 'une conversation sur les étoiles', 'une partie de cache-cache', 'une sieste sous une comète', 'une promenade dans le Jardin')
COSMIC_CHARACTERS = (
 ('🦆 Coin-Coin Ier', 'Le Canard Suprême réclame un ministère des flaques et des miettes.'),
 ('📚 Madame Paradoxe', 'La bibliothécaire veut récupérer un livre qui ne sera écrit que demain.'),
 ('🍞 Grille-Pain 3000', 'Le prophète du petit-déjeuner prédit une révolution des tartines.'),
 ('🪼 Professeur Gloups', 'La méduse astronome cherche ses lunettes dans une autre dimension.'),
 ('🧦 Ministre Chaussette', 'Un représentant du tiroir indépendant réclame un référendum.'),
)

def nox_wish(guild_id: int, day: str) -> str:
    # Une envie stable pour toute la journée, sans dépendance à une API.
    import hashlib
    n=int.from_bytes(hashlib.sha256(f'{guild_id}:{day}:nox'.encode()).digest()[:4], 'big')
    return NOX_WISHES[n % len(NOX_WISHES)]

def care_nox(conn, guild_id: int, user_id: int, action: str, day: str):
    if action not in NOX_EFFECTS:
        return False, 'Action inconnue.'
    c=creature(conn,guild_id)
    cur=conn.execute('INSERT OR IGNORE INTO cosmic_actions(guild_id,user_id,action,day) VALUES(?,?,?,?)',
                     (guild_id,user_id,'nox:'+action,day))
    if not cur.rowcount:
        return False, 'Nox a déjà partagé cette activité avec toi aujourd’hui. Essaie un autre bouton !'
    field,amount=NOX_EFFECTS[action]
    conn.execute(f'UPDATE cosmic_creature SET {field}=MIN(100,{field}+?), xp=xp+5, last_care=? WHERE guild_id=?',
                 (amount,day,guild_id))
    c=creature(conn,guild_id)
    stage=min(4,1+c['xp']//100)
    if stage>c['stage']:
        conn.execute('UPDATE cosmic_creature SET stage=?,last_evolution=? WHERE guild_id=?',(stage,day,guild_id))
        journal(conn,guild_id,f'Nox atteint le stade {stage} !')
    # Texte déterministe par jour / utilisateur / action, surprise sans incohérence.
    import hashlib
    seed=hashlib.sha256(f'{guild_id}:{user_id}:{day}:{action}'.encode()).digest()[0]
    line=NOX_LINES[action][seed%len(NOX_LINES[action])]
    if stage>c['stage']:
        line+=' 🌟 **Nox vient de se métamorphoser !**'
    return True,line


def map_text(conn,guild_id):
    n=progress(conn,guild_id)
    return '\n'.join(f'**{label}** — {desc}' if n>=required else f'🔒 Lieu secret · encore {required-n} anomalie(s)'
       for label,desc,required in PLACES.values())


def inventory_text(conn,guild_id,user_id):
    rows=conn.execute('SELECT item,quantity FROM cosmic_inventory WHERE guild_id=? AND user_id=? AND quantity>0 ORDER BY item',
                      (guild_id,user_id)).fetchall()
    return '\n'.join(f'• {r["item"]} × {r["quantity"]}' for r in rows) if rows else 'Ton sac est vide. Pars explorer !'


def visit_place(conn,guild_id,user_id,place,day):
    if place not in PLACES: return 'Ce lieu n’existe pas.'
    label,desc,needed=PLACES[place]
    if progress(conn,guild_id)<needed:return f'🔒 {label} est encore inaccessible.'
    cur=conn.execute('INSERT OR IGNORE INTO cosmic_actions VALUES(?,?,?,?)',
                     (guild_id,user_id,'visiter:'+place,day))
    if not cur.rowcount:return f'{label} — tu as déjà exploré ce lieu aujourd’hui.'
    item=random.choice(ARTIFACTS)
    conn.execute('INSERT INTO cosmic_inventory VALUES(?,?,?,1) ON CONFLICT(guild_id,user_id,item) DO UPDATE SET quantity=quantity+1',
                 (guild_id,user_id,item))
    return f'{label}\n{desc}\n✨ Tu découvres **{item}** !'


# V10.1 — Les missions, affinités et archives cachées.
# Les récompenses sont strictement cosmétiques et propres au Chaos Cosmique.
MISSION_TYPES = (
    ('parler', '💬 Confie un secret à Nox', 'Parle à Nox une fois aujourd’hui.'),
    ('nourrir', '🍪 Le goûter des étoiles', 'Offre à Nox un biscuit imaginaire.'),
    ('jouer', '🎲 Le championnat du n’importe quoi', 'Joue avec Nox.'),
    ('repos', '🌙 Une pause dans l’infini', 'Aide Nox à se reposer.'),
    ('explorer', '🧭 Mission comète', 'Pars explorer avec Nox.'),
)

def daily_mission(guild_id, user_id, day):
    import hashlib
    digest=hashlib.sha256(f'{guild_id}:{user_id}:{day}:mission:v1'.encode()).digest()
    return MISSION_TYPES[int.from_bytes(digest[:4], 'big') % len(MISSION_TYPES)]

def mission_status(conn, guild_id, user_id, day):
    action, title, desc = daily_mission(guild_id,user_id,day)
    completed = bool(conn.execute('SELECT 1 FROM cosmic_actions WHERE guild_id=? AND user_id=? AND action=? AND day=?',
                                  (guild_id,user_id,'nox:'+action,day)).fetchone())
    claimed = bool(conn.execute('SELECT 1 FROM cosmic_missions WHERE guild_id=? AND user_id=? AND day=? AND claimed_at IS NOT NULL',
                                (guild_id,user_id,day)).fetchone())
    return action,title,desc,completed,claimed

def claim_mission(conn,guild_id,user_id,day):
    action,title,desc,completed,claimed=mission_status(conn,guild_id,user_id,day)
    if claimed: return '🏅 Tu as déjà reçu la récompense de cette mission.'
    if not completed: return f'🧩 **{title}**\n{desc}\nReviens après avoir accompli cette action.'
    conn.execute('INSERT OR IGNORE INTO cosmic_missions(guild_id,user_id,day,mission) VALUES(?,?,?,?)',
                 (guild_id,user_id,day,action))
    cur=conn.execute('UPDATE cosmic_missions SET claimed_at=? WHERE guild_id=? AND user_id=? AND day=? AND claimed_at IS NULL',
                     (datetime.now(LOCAL_TIMEZONE).isoformat(),guild_id,user_id,day))
    if not cur.rowcount: return '🏅 Cette mission a déjà été récompensée.'
    item='éclat de destinée'
    conn.execute('INSERT INTO cosmic_inventory VALUES(?,?,?,1) ON CONFLICT(guild_id,user_id,item) DO UPDATE SET quantity=quantity+1',
                 (guild_id,user_id,item))
    return f'🏆 **{title} accomplie !**\nTu gagnes un **{item}**. Il ne sert à rien de raisonnable… pour le moment.'

def encounter_character(conn,guild_id,user_id,day):
    import hashlib
    seed=hashlib.sha256(f'{guild_id}:{user_id}:{day}:rencontre'.encode()).digest()[0]
    name,story=COSMIC_CHARACTERS[seed%len(COSMIC_CHARACTERS)]
    conn.execute('INSERT OR IGNORE INTO cosmic_bonds(guild_id,user_id,character) VALUES(?,?,?)', (guild_id,user_id,name))
    cur=conn.execute('UPDATE cosmic_bonds SET affinity=MIN(10,affinity+1),last_meeting=? '
                     'WHERE guild_id=? AND user_id=? AND character=? AND last_meeting!=?',
                     (day,guild_id,user_id,name,day))
    bond=conn.execute('SELECT affinity FROM cosmic_bonds WHERE guild_id=? AND user_id=? AND character=?',
                      (guild_id,user_id,name)).fetchone()['affinity']
    suffix='\n💫 Cette rencontre renforce votre complicité.' if cur.rowcount else '\n⏳ Vous vous êtes déjà rencontrés aujourd’hui.'
    if bond>=3:
        secret='le protocole des miettes'
        stamp=datetime.now(LOCAL_TIMEZONE).isoformat()
        unlocked=conn.execute('INSERT OR IGNORE INTO cosmic_secrets VALUES(?,?,?,?)',
                              (guild_id,user_id,secret,stamp))
        if unlocked.rowcount:
            suffix+='\n🔐 **SECRET DÉCOUVERT :** Le protocole des miettes. Quelqu’un a dissimulé les clés du cosmos dans une boîte à biscuits.'
    return f'🎭 **{name}**\n{story}\n💞 Affinité : **{bond}/10**'+suffix

def archive_text(conn,guild_id,user_id):
    rows=conn.execute('SELECT secret,discovered_at FROM cosmic_secrets WHERE guild_id=? AND user_id=? ORDER BY discovered_at',
                      (guild_id,user_id)).fetchall()
    return ('\n'.join('🔓 '+r['secret'].title() for r in rows) if rows else
            '🔒 Aucun secret découvert pour le moment. Rencontrer régulièrement les habitants pourrait aider…')

# V10.2 — saisons et expéditions accessibles par boutons, sans API externe.
# Une saison dure 28 jours UTC-localisés à Paris; son numéro reste stable pour une date.
SEASON_STORIES = (
    ('🌠 Le Grand Réveil', 'L’Observatoire a reçu une lettre signée par une étoile qui n’existe pas. Nox veut répondre.'),
    ('⏳ La Guerre des Horloges', 'Madame Paradoxe a perdu demain. Le Canard Suprême accuse officiellement mercredi.'),
    ('🎪 Le Carnaval du Néant', 'Un cirque a débarqué avec des billets gratuits, mais personne ne sait où se trouve l’entrée.'),
    ('🦆 Le Ministère des Miettes', 'Coin-Coin Ier exige un recensement de toutes les tartines interstellaires.'),
)
COSMIC_RUMORS = (
    'Une porte ne s’ouvre qu’aux personnes qui savent saluer un caillou.',
    'Le Grille-Pain 3000 a prédit une pluie de croissants sur l’Observatoire.',
    'Une des étoiles serait en réalité un bouton de manchette perdu.',
    'Le Professeur Gloups cache une carte dans une bulle de savon.',
    'Nox affirme avoir entendu une comète demander son chemin.',
    'Le Canard Suprême aurait engagé une armée de parapluies.',
    'Madame Paradoxe emprunte parfois des livres à elle-même dans le futur.',
)

def cosmic_season(day):
    from datetime import date
    d=date.fromisoformat(day)
    return (d-date(2026, 1, 1)).days // 28

def season_overview(conn,guild_id,day):
    season=cosmic_season(day)
    title,story=SEASON_STORIES[season % len(SEASON_STORIES)]
    row=conn.execute('SELECT contributions,completed_at FROM cosmic_expeditions WHERE guild_id=? AND season=?',
                     (guild_id,season)).fetchone()
    total=row['contributions'] if row else 0
    return season,title,story,total, bool(row and row['completed_at'])

def cosmic_rumor(guild_id,user_id,day):
    import hashlib
    seed=hashlib.sha256(f'{guild_id}:{user_id}:{day}:rumeur:v102'.encode()).digest()
    return COSMIC_RUMORS[int.from_bytes(seed[:4],'big')%len(COSMIC_RUMORS)]

def contribute_expedition(conn,guild_id,user_id,day):
    season,title,story,total,done=season_overview(conn,guild_id,day)
    if done:
        return f'🏆 **{title}**\nL’expédition est terminée ! Reviens à la prochaine saison.'
    cur=conn.execute('INSERT OR IGNORE INTO cosmic_expedition_actions VALUES(?,?,?,?)',
                     (guild_id,user_id,day,season))
    if not cur.rowcount:
        return f'⏳ Tu as déjà aidé l’expédition aujourd’hui. Progression : **{total}/12**.'
    conn.execute('INSERT OR IGNORE INTO cosmic_expeditions(guild_id,season) VALUES(?,?)',(guild_id,season))
    conn.execute('UPDATE cosmic_expeditions SET contributions=MIN(12,contributions+1) WHERE guild_id=? AND season=?',
                 (guild_id,season))
    row=conn.execute('SELECT contributions FROM cosmic_expeditions WHERE guild_id=? AND season=?',(guild_id,season)).fetchone()
    count=row['contributions']
    if count>=12:
        conn.execute('UPDATE cosmic_expeditions SET completed_at=? WHERE guild_id=? AND season=? AND completed_at IS NULL',
                     (datetime.now(LOCAL_TIMEZONE).isoformat(),guild_id,season))
        journal(conn,guild_id,f'🏆 Expédition collective achevée : {title}')
        return f'🌟 **{title} — expédition accomplie !**\nLes 12 éclats ont été réunis. Une nouvelle page des Chroniques s’ouvre.'
    return f'✨ Tu apportes un éclat à **{title}** !\nProgression collective : **{count}/12**. Même en solo, une contribution par jour suffit.'

# V10.3 — Le Portail des Paradoxes : mini-aventures à embranchements.
# Le tirage est déterministe par membre/jour ; un choix est sauvegardé une seule fois.
PARADOX_SCENES = (
    ('miettes', '🦆 Le Bureau des Miettes Disparues',
     'Coin-Coin Ier accuse une comète d’avoir volé son petit déjeuner.',
     ('Défendre la comète', 'Interroger le grille-pain', 'Proposer une médiation'),
     ('La comète est acquittée. Elle t’offre un timbre stellaire.',
      'Grille-Pain 3000 avoue avoir téléporté les tartines. Il te remet un reçu impossible.',
      'Le tribunal signe la paix des croissants. Tu reçois un ruban diplomatique.')),
    ('temps', '⏳ Le Mardi de Rechange',
     'Madame Paradoxe a trouvé un mardi supplémentaire derrière une étagère.',
     ('Le rendre au calendrier', 'Le garder en souvenir', 'Le donner à Nox'),
     ('Le calendrier te remercie avec une aiguille de minuit.',
      'Ton mardi miniature tient dans une poche. Tu trouves une minute pliée.',
      'Nox le transforme en mercredi moelleux. Tu gagnes un fragment de demain.')),
    ('gloups', '🪼 La Conférence des Bulles',
     'Le Professeur Gloups organise une conférence scientifique sous l’eau, dans l’espace.',
     ('Poser une question', 'Tester son invention', 'Inviter Nox à parler'),
     ('La réponse tient dans une bulle savante. Tu la conserves précieusement.',
      'La machine produit un soupir de nébuleuse. Tu emportes un boulon poétique.',
      'Nox prononce un discours sur les biscuits. Tu gagnes une médaille de patience.')),
    ('jardin', '🌱 La Révolte des Géraniums Stellaires',
     'Les fleurs du jardin exigent de choisir elles-mêmes leur prénom.',
     ('Organiser un vote', 'Écouter leurs souhaits', 'Faire appel au Canard'),
     ('Le vote élit Gérard Premier. Une graine de démocratie t’est offerte.',
      'Les fleurs choisissent toutes « Gérard ». Tu reçois une feuille enchantée.',
      'Le Canard proclame la République des Pots. Tu obtiens un sceau de terre.')),
)

def paradox_scene(guild_id,user_id,day):
    import hashlib
    digest=hashlib.sha256(f'{guild_id}:{user_id}:{day}:paradoxe:v103'.encode()).digest()
    return PARADOX_SCENES[int.from_bytes(digest[:4],'big')%len(PARADOX_SCENES)]

def paradox_status(conn,guild_id,user_id,day):
    scene=paradox_scene(guild_id,user_id,day)
    row=conn.execute('SELECT choice,result FROM cosmic_paradox_choices WHERE guild_id=? AND user_id=? AND day=?',
                     (guild_id,user_id,day)).fetchone()
    return scene,row

def choose_paradox(conn,guild_id,user_id,day,choice):
    if choice not in (0,1,2): return 'Ce choix est inconnu.'
    scene,row=paradox_status(conn,guild_id,user_id,day)
    if row: return '📖 Ton histoire du jour est déjà écrite : '+row['result']
    result=scene[4][choice]
    cur=conn.execute('INSERT OR IGNORE INTO cosmic_paradox_choices VALUES(?,?,?,?,?,?)',
                     (guild_id,user_id,day,scene[0],choice,result))
    if not cur.rowcount:
        row=conn.execute('SELECT result FROM cosmic_paradox_choices WHERE guild_id=? AND user_id=? AND day=?',
                         (guild_id,user_id,day)).fetchone()
        return '📖 Ton histoire est déjà écrite : '+row['result']
    # Une découverte personnelle, non destructive, limitée à une par jour.
    artifact=('timbre du paradoxe','souvenir temporel','bulle d’impossible')[choice]
    conn.execute('INSERT INTO cosmic_inventory VALUES(?,?,?,1) ON CONFLICT(guild_id,user_id,item) DO UPDATE SET quantity=quantity+1',
                 (guild_id,user_id,artifact))
    return f'✨ **{result}**\n🎒 Objet obtenu : **{artifact}**.\nReviens demain pour une nouvelle histoire !'

# V10.4 — Intrigues croisées : scènes déterministes, sans appel à une API externe.
CROSSROADS = (
    ('miettes', '🦆 Le scandale des miettes disparues',
     'Coin-Coin Ier accuse Grille-Pain 3000 de détourner les réserves de biscuits stellaires. Nox affirme avoir vu une tartine fuir à cheval.',
     ('Inspecter le grille-pain', 'Défendre le canard', 'Demander à Nox de négocier'),
     (('Le grille-pain avoue avoir fondé une banque de croûtons. Madame Paradoxe exige un audit rétroactif.', -3, 5, 5, 'Grille-Pain 3000'),
      ('Coin-Coin Ier est nommé ministre des miettes, mais doit désormais déclarer chaque biscotte.', 5, 3, 2, 'Coin-Coin Ier'),
      ('Nox organise une paix autour du goûter. Les tartines obtiennent le droit de vote.', -5, 5, 9, 'Nox'))),
    ('livre', '📚 Le livre qui a avalé demain',
     'Madame Paradoxe a prêté un livre au Professeur Gloups. Depuis, Nox reçoit des lettres de son futur lui.',
     ('Rendre le livre', 'Étudier les lettres', 'Faire lire Nox'),
     (('Le livre revient avec 48 heures de retard avant son départ. La bibliothèque applaudit.', -3, 4, 7, 'Madame Paradoxe'),
      ('Gloups découvre une équation écrite en confiture. Elle fonctionne uniquement les jeudis.', 4, 8, 3, 'Professeur Gloups'),
      ('Nox apprend le mot « ploufologie ». Il réclame immédiatement un diplôme.', 6, 7, 5, 'Nox'))),
    ('couronne', '👑 La couronne des trois catastrophes',
     'Le Canard Suprême veut faire couronner Nox par un grille-pain, pendant que Madame Paradoxe annonce que la cérémonie a déjà eu lieu demain.',
     ('Organiser un vote', 'Annuler la cérémonie', 'Couronner une chaussette'),
     (('Les habitants votent pour une république de peluches. Le canard demande un recomptage.', -2, 5, 8, 'Coin-Coin Ier'),
      ('Madame Paradoxe annule la cérémonie avant son annonce. Personne ne sait qui doit rembourser le gâteau.', -5, 4, 7, 'Madame Paradoxe'),
      ('Une chaussette devient souveraine. Nox est nommé ministre des câlins.', 9, 6, 4, 'Nox'))),
    ('etoile', '✨ L’étoile qui voulait démissionner',
     'Le Professeur Gloups découvre qu’une étoile souhaite devenir veilleuse. Grille-Pain 3000 propose de la recruter pour cuire du pain.',
     ('Respecter son choix', 'Créer une école d’étoiles', 'Lui présenter Nox'),
     (('L’étoile éclaire désormais une bibliothèque miniature. Gloups pleure de joie.', -4, 3, 9, 'Professeur Gloups'),
      ('La première école de reconversion stellaire ouvre dans une tasse de thé.', -2, 7, 7, 'Madame Paradoxe'),
      ('Nox et l’étoile deviennent amis. Une nouvelle constellation dessine un biscuit.', 2, 8, 8, 'Nox'))),
)


def crossroad_scene(guild_id, user_id, day):
    import hashlib
    digest = hashlib.sha256(f'{guild_id}:{user_id}:{day}:croisement:v104'.encode()).digest()
    return CROSSROADS[int.from_bytes(digest[:4], 'big') % len(CROSSROADS)]


def crossroad_status(conn, guild_id, user_id, day):
    scene = crossroad_scene(guild_id, user_id, day)
    row = conn.execute('SELECT * FROM cosmic_crossroads WHERE guild_id=? AND user_id=? AND day=?',
                       (guild_id, user_id, day)).fetchone()
    return scene, row


def choose_crossroad(conn, guild_id, user_id, day, choice):
    if choice not in (0, 1, 2):
        raise ValueError('Choix invalide')
    scene, previous = crossroad_status(conn, guild_id, user_id, day)
    if previous:
        return previous['outcome'], False
    outcome, dc, de, dh, character = scene[4][choice]
    # SQLite sérialise l'écriture et empêche de créditer deux fois un même choix.
    inserted = conn.execute('INSERT OR IGNORE INTO cosmic_crossroads VALUES(?,?,?,?,?,?)',
                            (guild_id, user_id, day, scene[0], choice, outcome)).rowcount
    if not inserted:
        row = conn.execute('SELECT outcome FROM cosmic_crossroads WHERE guild_id=? AND user_id=? AND day=?',
                           (guild_id, user_id, day)).fetchone()
        return row['outcome'], False
    ensure_world(conn, guild_id)
    conn.execute('UPDATE cosmic_world SET chaos=MAX(0,MIN(100,chaos+?)), energy=MAX(0,MIN(100,energy+?)), harmony=MAX(0,MIN(100,harmony+?)) WHERE guild_id=?',
                 (dc, de, dh, guild_id))
    conn.execute('INSERT OR IGNORE INTO cosmic_bonds(guild_id,user_id,character) VALUES(?,?,?)',
                 (guild_id,user_id,character))
    conn.execute('UPDATE cosmic_bonds SET affinity=MIN(10,affinity+1) WHERE guild_id=? AND user_id=? AND character=?',
                 (guild_id,user_id,character))
    conn.execute('INSERT INTO cosmic_journal(guild_id,at,entry) VALUES(?,?,?)',
                 (guild_id,datetime.now(LOCAL_TIMEZONE).isoformat(),f'Intrigue croisée : {scene[1]} — {outcome}'))
    # La conséquence se manifestera deux jours plus tard, une seule fois.
    due = (datetime.fromisoformat(day).date() + timedelta(days=2)).isoformat()
    conn.execute('INSERT OR IGNORE INTO cosmic_echoes(guild_id,user_id,source_day,due_day,arc_key,choice) VALUES(?,?,?,?,?,?)',
                 (guild_id,user_id,day,due,scene[0],choice))
    return outcome, True


ECHO_TWISTS = (
    'Une lettre scellée arrive à l’Observatoire. Elle porte ton nom et la signature d’un canard qui nie tout.',
    'Nox retrouve une petite boîte oubliée : elle contient une promesse et trois miettes stellaires.',
    'Madame Paradoxe affirme que ton choix a créé un nouveau souvenir dans les archives.',
    'Grille-Pain 3000 publie une prophétie à ton sujet. Elle est écrite sur une biscotte.',
    'Le Professeur Gloups t’envoie un certificat de diplomatie cosmique, signé à l’envers.',
)


def resolve_due_echoes(conn, guild_id, today):
    """Résout les retours arrivés à échéance, sans doublon même après redémarrage."""
    import hashlib
    rows = conn.execute('SELECT * FROM cosmic_echoes WHERE guild_id=? AND status=? AND due_day<=? ORDER BY due_day,source_day',
                        (guild_id,'pending',today)).fetchall()
    results = []
    for row in rows:
        seed = f'{row["guild_id"]}:{row["user_id"]}:{row["source_day"]}:{row["arc_key"]}:{row["choice"]}'
        index = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], 'big') % len(ECHO_TWISTS)
        text = ECHO_TWISTS[index]
        updated = conn.execute('UPDATE cosmic_echoes SET status=?,result=? WHERE guild_id=? AND user_id=? AND source_day=? AND status=?',
                               ('ready',text,guild_id,row['user_id'],row['source_day'],'pending')).rowcount
        if updated:
            conn.execute('INSERT INTO cosmic_journal(guild_id,at,entry) VALUES(?,?,?)',
                         (guild_id,datetime.now(LOCAL_TIMEZONE).isoformat(),f'Écho différé de {row["arc_key"]} : {text}'))
            results.append((row['user_id'],text))
    return results


def echo_inbox(conn, guild_id, user_id, today):
    resolve_due_echoes(conn,guild_id,today)
    ready = conn.execute('SELECT source_day,result FROM cosmic_echoes WHERE guild_id=? AND user_id=? AND status=? ORDER BY due_day DESC LIMIT 5',
                         (guild_id,user_id,'ready')).fetchall()
    waiting = conn.execute('SELECT due_day FROM cosmic_echoes WHERE guild_id=? AND user_id=? AND status=? ORDER BY due_day LIMIT 1',
                           (guild_id,user_id,'pending')).fetchone()
    lines = [f'✨ **Écho du {r["source_day"]}** — {r["result"]}' for r in ready]
    if waiting:
        lines.append(f'⏳ Une conséquence se prépare pour le {waiting["due_day"]}.')
    return '\n\n'.join(lines) if lines else 'Aucun écho pour le moment. Les choix des intrigues peuvent revenir te surprendre deux jours plus tard.'


class CosmicCrossroadSelect(discord.ui.Select):
    def __init__(self, scene):
        super().__init__(placeholder='Choisis la suite de cette histoire…', min_values=1, max_values=1,
                         options=[discord.SelectOption(label=label, value=str(index)) for index,label in enumerate(scene[3])])

    async def callback(self, interaction):
        if not interaction.guild:
            return await interaction.response.send_message('Disponible uniquement sur un serveur.', ephemeral=True)
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            result, changed=choose_crossroad(conn,interaction.guild.id,interaction.user.id,day,int(self.values[0]))
        await interaction.response.send_message(('✨ **Ton choix change le cosmos !**\n' if changed else '📖 **Déjà résolu aujourd’hui.**\n')+result,ephemeral=True)


class CosmicCrossroadView(discord.ui.View):
    def __init__(self,scene):
        super().__init__(timeout=300)
        self.add_item(CosmicCrossroadSelect(scene))


async def show_crossroad(interaction):
    if not interaction.guild:
        return await interaction.response.send_message('Disponible uniquement sur un serveur.',ephemeral=True)
    day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
    with connect() as conn:
        scene,row=crossroad_status(conn,interaction.guild.id,interaction.user.id,day)
    if row:
        return await interaction.response.send_message(f'📖 **{scene[1]}**\n{row["outcome"]}\nUne nouvelle intrigue t’attendra demain.',ephemeral=True)
    await interaction.response.send_message(f'🎭 **{scene[1]}**\n{scene[2]}\n\n**À toi de décider !**',view=CosmicCrossroadView(scene),ephemeral=True)


class CosmicParadoxView(discord.ui.View):
    def __init__(self,scene):
        super().__init__(timeout=180)
        self.add_item(CosmicParadoxSelect(scene))

class CosmicParadoxSelect(discord.ui.Select):
    def __init__(self,scene):
        super().__init__(placeholder='🔮 Choisir le destin de cette histoire', min_values=1,max_values=1,
                         options=[discord.SelectOption(label=label[:100],value=str(n)) for n,label in enumerate(scene[3],1)])
    async def callback(self,interaction):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            scene,row=paradox_status(conn,interaction.guild.id,interaction.user.id,day)
            # Le menu est personnel et éphémère ; la base refuse les doubles choix.
            result=choose_paradox(conn,interaction.guild.id,interaction.user.id,day,int(self.values[0])-1)
        await interaction.response.send_message(result,ephemeral=True)

async def show_paradox(interaction):
    day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
    with connect() as conn:
        scene,row=paradox_status(conn,interaction.guild.id,interaction.user.id,day)
    if row:
        return await interaction.response.send_message(f'🔮 **{scene[1]}**\n📖 {row["result"]}\nReviens demain pour un nouveau paradoxe.',ephemeral=True)
    choices='\n'.join(f'**{idx}.** {name}' for idx,name in enumerate(scene[3],1))
    await interaction.response.send_message(f'🔮 **{scene[1]}**\n{scene[2]}\n\n{choices}\n\n*Une décision par jour, sans retour en arrière.*',view=CosmicParadoxView(scene),ephemeral=True)

class CosmicExpeditionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
    @discord.ui.button(label='Apporter un éclat',emoji='✨',style=discord.ButtonStyle.success)
    async def contribute(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            message=contribute_expedition(conn,i.guild.id,i.user.id,day)
        await i.response.send_message(message,ephemeral=True)

class NoxPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def action(self,interaction,action):
        if not interaction.guild:
            return await interaction.response.send_message('Disponible sur le serveur uniquement.',ephemeral=True)
        with connect() as conn:
            ok,message=care_nox(conn,interaction.guild.id,interaction.user.id,action,datetime.now(LOCAL_TIMEZONE).date().isoformat())
            c=creature(conn,interaction.guild.id)
        await interaction.response.send_message(('👾 ' if ok else '⏳ ')+message,embed=creature_embed(c) if ok else None,ephemeral=True)

    @discord.ui.button(label='Nourrir',emoji='🍪',style=discord.ButtonStyle.success,custom_id='cosmic:v10:nox:feed',row=0)
    async def feed(self,i,b): await self.action(i,'nourrir')
    @discord.ui.button(label='Lui parler',emoji='💬',style=discord.ButtonStyle.primary,custom_id='cosmic:v10:nox:talk',row=0)
    async def talk(self,i,b): await self.action(i,'parler')
    @discord.ui.button(label='Jouer',emoji='🎲',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:play',row=0)
    async def play(self,i,b): await self.action(i,'jouer')
    @discord.ui.button(label='Se reposer',emoji='🌙',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:rest',row=0)
    async def rest(self,i,b): await self.action(i,'repos')
    @discord.ui.button(label='Explorer avec Nox',emoji='🧭',style=discord.ButtonStyle.primary,custom_id='cosmic:v10:nox:explore',row=1)
    async def explore(self,i,b): await self.action(i,'explorer')
    @discord.ui.button(label='Carte du monde',emoji='🗺️',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:map',row=1)
    async def map(self,i,b):
        with connect() as conn:
            ensure_world(conn,i.guild.id)
            text=map_text(conn,i.guild.id)
        await i.response.send_message('🗺️ **Le monde à découvrir**\n'+text,view=CosmicExplore(),ephemeral=True)
    @discord.ui.button(label='Échos du destin',emoji='✉️',style=discord.ButtonStyle.secondary,custom_id='cosmic:v105:nox:echoes',row=1)
    async def echoes(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            msg=echo_inbox(conn,i.guild.id,i.user.id,day)
        await i.response.send_message('✉️ **Les échos de tes décisions**\n'+msg,ephemeral=True)

    @discord.ui.button(label='Mon sac',emoji='🎒',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:bag',row=1)
    async def bag(self,i,b):
        with connect() as conn: text=inventory_text(conn,i.guild.id,i.user.id)
        await i.response.send_message('🎒 **Tes trésors**\n'+text,ephemeral=True)
    @discord.ui.button(label='Chroniques',emoji='📜',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:chronicles',row=2)
    async def chronicles(self,i,b):
        with connect() as conn:
            unlocks(conn,i.guild.id)
            rows=conn.execute('SELECT chapter FROM cosmic_chapters WHERE guild_id=? ORDER BY chapter',(i.guild.id,)).fetchall()
        text='\n\n'.join(f'**{CHAPTERS[r["chapter"]][0]}** — {CHAPTERS[r["chapter"]][1]}' for r in rows)
        await i.response.send_message('📜 **Chroniques**\n'+(text or 'Les pages sont encore vierges.'),ephemeral=True)
    @discord.ui.button(label='Rencontre surprise',emoji='🎭',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:nox:encounter',row=2)
    async def encounter(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            msg=encounter_character(conn,i.guild.id,i.user.id,day)
        await i.response.send_message(msg,ephemeral=True)


    @discord.ui.button(label='Intrigue des habitants',emoji='🎭',style=discord.ButtonStyle.primary,custom_id='cosmic:v104:nox:crossroad',row=2)
    async def crossroad(self,i,b):
        await show_crossroad(i)

    @discord.ui.button(label='Mission du jour',emoji='🏅',style=discord.ButtonStyle.success,custom_id='cosmic:v101:nox:mission',row=3)
    async def mission(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            action,title,desc,done,claimed=mission_status(conn,i.guild.id,i.user.id,day)
        status='🏆 Récompense récupérée' if claimed else '✅ Prête à être récupérée' if done else '⏳ À accomplir'
        await i.response.send_message(f'🏅 **{title}**\n{desc}\n**{status}**',view=CosmicMissionClaim(),ephemeral=True)

    @discord.ui.button(label='Mes secrets',emoji='🔐',style=discord.ButtonStyle.secondary,custom_id='cosmic:v101:nox:secrets',row=3)
    async def secrets(self,i,b):
        with connect() as conn: msg=archive_text(conn,i.guild.id,i.user.id)
        await i.response.send_message('📖 **Les Archives de l’Impossible**\n'+msg,ephemeral=True)

    @discord.ui.button(label='Mes rencontres',emoji='💞',style=discord.ButtonStyle.secondary,custom_id='cosmic:v101:nox:bonds',row=3)
    async def bonds(self,i,b):
        with connect() as conn:
            rows=conn.execute('SELECT character,affinity FROM cosmic_bonds WHERE guild_id=? AND user_id=? ORDER BY affinity DESC,character',
                              (i.guild.id,i.user.id)).fetchall()
        msg='\n'.join(f'• {r["character"]} — {r["affinity"]}/10' for r in rows) or 'Tu n’as encore rencontré personne.'
        await i.response.send_message('💞 **Tes rencontres cosmiques**\n'+msg,ephemeral=True)

    @discord.ui.button(label='Saison actuelle',emoji='🌠',style=discord.ButtonStyle.primary,custom_id='cosmic:v102:nox:season',row=4)
    async def season(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            season,title,story,total,done=season_overview(conn,i.guild.id,day)
        await i.response.send_message(f'🌌 **{title}**\n{story}\n\n✨ Expédition : **{total}/12**'+(' — terminée !' if done else ''),view=CosmicExpeditionView(),ephemeral=True)

    @discord.ui.button(label='Portail des paradoxes',emoji='🔮',style=discord.ButtonStyle.secondary,custom_id='cosmic:v102:nox:rumor',row=4)
    async def rumor(self,i,b):
        await show_paradox(i)

    @discord.ui.button(label='Expédition',emoji='🚀',style=discord.ButtonStyle.success,custom_id='cosmic:v102:nox:expedition',row=4)
    async def expedition(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            season,title,story,total,done=season_overview(conn,i.guild.id,day)
        await i.response.send_message(f'🚀 **Expédition : {title}**\nRéunissez **12 éclats** pour terminer la quête.\nProgression : **{total}/12**'+(' 🏆' if done else ''),view=CosmicExpeditionView(),ephemeral=True)

    @discord.ui.button(label='NOX TV · Staff',emoji='🎬',style=discord.ButtonStyle.secondary,custom_id='cosmic:v1041:nox:noxtv',row=4)
    async def noxtv_staff(self,i,b):
        if not i.guild or not i.user.guild_permissions.manage_guild:
            await i.response.send_message('🛡️ Ce panneau est réservé au staff.',ephemeral=True)
            return
        from .nox_tv import NoxTVDashboard
        embed=horizons_embed(title='🎬 NOX TV — Tableau de bord',
            description='Statut, diagnostic, audit, simulation et catalogue. Aucune publication automatique n’est déclenchée ici.',color=0x7764ff)
        await i.response.send_message(embed=embed,view=NoxTVDashboard(),ephemeral=True)

# Centre unique : les menus ouvrent des sous-panneaux privés, sans publier.
NOX_SECTIONS = {
    'accueil': ('🐾 Centre NOX', 'Choisis une rubrique ci-dessous. Les panneaux restent privés et ne publient rien.'),
    'univers': ('🌌 Univers cosmique', 'Soins, exploration, rencontres, missions et chroniques du monde de NOX.'),
    'refuge': ('🏡 Refuge', 'Retrouve le panneau du Refuge et ses six soins. Les rôles et souvenirs restent conservés.'),
    'animations': ('🎲 Animations', 'Sondages, défis, aventures, missions collectives et surprises.'),
    'publications': ('📬 Publications', '12 rendez-vous de 10h à 22h50, dont 6 illustrés. Les sondages et défis occupent des créneaux existants.'),
    'tv': ('🎬 NOX TV', 'Catalogue, diagnostics, simulations, votes et contrôle des publications visuelles.'),
    'administration': ('🛡️ Administration NOX', 'Planning, diagnostic, activation du quotidien et réglages. Aucun envoi ne part de ce tableau de bord.'),
}


def nox_dashboard_embed(section):
    title, description = NOX_SECTIONS[section]
    embed = horizons_embed(title=title, description=description, color=0xD4AF37)
    if section == 'accueil':
        embed.add_field(name='🧭 Navigation', value='Univers · Refuge · Animations · Publications · NOX TV · Administration', inline=False)
    elif section == 'publications':
        embed.add_field(name='📅 Programme', value='10h00–22h50 · 12 créneaux · 6 images · 2 sondages · 1 défi · 1 bilan', inline=False)
    elif section == 'animations':
        embed.add_field(name='🌟 Participer', value='Les membres votent et participent dans les messages de NOX. Les administrateurs pilotent les animations depuis les outils existants.', inline=False)
    elif section == 'administration':
        embed.add_field(name='🔒 Accès', value='Les contrôles sont réservés aux administrateurs. Les autres membres ne peuvent pas les déclencher.', inline=False)
    return embed


class NoxCentralSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=title.split(' ', 1)[1], value=key, emoji=title.split(' ', 1)[0])
                   for key, (title, _) in NOX_SECTIONS.items()]
        super().__init__(placeholder='Choisir une rubrique de NOX', options=options, row=0)

    async def callback(self, interaction):
        view = self.view
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message('Ouvre ton propre centre avec `/nox`.', ephemeral=True)
        view.section = self.values[0]
        view.refresh()
        await interaction.response.edit_message(embed=nox_dashboard_embed(view.section), view=view)


class NoxDailyConfigModal(discord.ui.Modal, title='Configurer les publications de NOX'):
    channel_id = discord.ui.TextInput(label='Identifiant du salon de publication', placeholder='ID numérique du salon', min_length=15, max_length=22)
    active = discord.ui.TextInput(label='Activer ? (oui / non)', placeholder='oui', min_length=2, max_length=3)

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Accès administrateur requis.', ephemeral=True)
        raw = str(self.channel_id).strip()
        answer = str(self.active).strip().lower()
        if not raw.isdecimal() or answer not in ('oui', 'non'):
            return await interaction.response.send_message('Indique un ID numérique et « oui » ou « non ».', ephemeral=True)
        channel = interaction.guild.get_channel(int(raw))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message('Salon textuel introuvable sur ce serveur.', ephemeral=True)
        member = interaction.guild.me
        perms = channel.permissions_for(member) if member else None
        if not perms or not (perms.view_channel and perms.send_messages and perms.manage_webhooks and perms.attach_files):
            return await interaction.response.send_message('Permissions requises : voir, écrire, gérer les webhooks et joindre des fichiers.', ephemeral=True)
        from .nox_refuge import DB
        from . import nox_refuge_engine as engine
        from .nox_daily_12 import initialize
        with engine.connect(DB) as con:
            initialize(con)
            con.execute('INSERT INTO nox_daily_config(guild_id,channel_id,enabled) VALUES(?,?,?) '
                        'ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id,enabled=excluded.enabled',
                        (interaction.guild.id, channel.id, int(answer == 'oui')))
            con.commit()
        await interaction.response.send_message(
            f'🐾 Publications {"activées" if answer == "oui" else "suspendues"} dans {channel.mention}. '
            'Les horaires existants restent inchangés.', ephemeral=True)


class NoxActivityModal(discord.ui.Modal, title='NOX — interventions spontanées'):
    channel_id = discord.ui.TextInput(label='Identifiant du salon', placeholder='ID du salon Discord', min_length=15, max_length=22)
    active = discord.ui.TextInput(label='Activer (oui/non)', placeholder='non', min_length=2, max_length=3)

    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé aux administrateurs.', ephemeral=True)
        raw, answer = str(self.channel_id).strip(), str(self.active).strip().lower()
        if not raw.isdecimal() or answer not in ('oui', 'non'):
            return await interaction.response.send_message('Indique un ID de salon et oui ou non.', ephemeral=True)
        channel = interaction.guild.get_channel(int(raw))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message('Salon textuel introuvable.', ephemeral=True)
        cog = interaction.client.get_cog('NoxPresence' if self.kind == 'presence' else 'NoxLife')
        if not cog:
            return await interaction.response.send_message('Module indisponible.', ephemeral=True)
        handler = cog.noxpresence if self.kind == 'presence' else cog.noxvie
        await handler(interaction, channel, answer == 'oui')


class NoxEventsModal(discord.ui.Modal, title='NOX — événements'):
    birthdays = discord.ui.TextInput(label='Anniversaires (oui/non)', placeholder='non', min_length=2, max_length=3)
    quizzes = discord.ui.TextInput(label='Quiz (oui/non)', placeholder='non', min_length=2, max_length=3)

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé aux administrateurs.', ephemeral=True)
        values = [str(self.birthdays).strip().lower(), str(self.quizzes).strip().lower()]
        if any(v not in ('oui', 'non') for v in values):
            return await interaction.response.send_message('Réponds oui ou non aux deux champs.', ephemeral=True)
        cog = interaction.client.get_cog('NoxEvents')
        if not cog:
            return await interaction.response.send_message('Module indisponible.', ephemeral=True)
        await cog.noxevenements(interaction, *(v == 'oui' for v in values))


class NoxSurpriseSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='Choisir une surprise à publier dans ce salon', options=[
            discord.SelectOption(label='Absurdité cosmique', value='absurde', emoji='🪐'),
            discord.SelectOption(label='Question loufoque', value='question', emoji='❓'),
            discord.SelectOption(label='Mini-défi collectif', value='defi', emoji='🎲'),
            discord.SelectOption(label='Douceur de NOX', value='douceur', emoji='💛'),
        ])

    async def callback(self, interaction):
        if interaction.user.id != self.view.owner_id or not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé à l’administrateur ayant ouvert le panneau.', ephemeral=True)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message('Ouvre le panneau dans un salon textuel.', ephemeral=True)
        cog = interaction.client.get_cog('NoxSurprises')
        if not cog:
            return await interaction.response.send_message('Module indisponible.', ephemeral=True)
        choice = app_commands.Choice(name=self.values[0], value=self.values[0])
        await cog.noxsurprise(interaction, choice, interaction.channel)


class NoxSurpriseView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(NoxSurpriseSelect())


class NoxRolesSyncModal(discord.ui.Modal, title='NOX — synchronisation des rôles'):
    offset = discord.ui.TextInput(label='Début de pagination (0, 100, 200...)', default='0', max_length=6)

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé aux administrateurs.', ephemeral=True)
        raw = str(self.offset).strip()
        if not raw.isdecimal() or int(raw) > 100000:
            return await interaction.response.send_message('Indique un nombre entre 0 et 100000.', ephemeral=True)
        cog = interaction.client.get_cog('NoxHonorRoles')
        if cog is None:
            return await interaction.response.send_message('Module de rôles indisponible.', ephemeral=True)
        await cog.noxroles(interaction, app_commands.Choice(name='Synchroniser', value='synchroniser'), int(raw))


class NoxSpeakModal(discord.ui.Modal, title='NOX — message personnalisé'):
    texte = discord.ui.TextInput(label='Message de NOX', style=discord.TextStyle.paragraph, min_length=1, max_length=1800)

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé aux administrateurs.', ephemeral=True)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message('Utilise un salon textuel.', ephemeral=True)
        cog = interaction.client.get_cog('NoxPublications')
        if cog is None:
            return await interaction.response.send_message('Module de publication indisponible.', ephemeral=True)
        await cog.me(interaction, str(self.texte), interaction.channel)


class NoxManualSelect(discord.ui.Select):
    def __init__(self):
        import json
        from pathlib import Path
        catalogue = Path(__file__).resolve().parent.parent / 'data' / 'nox' / 'messages_manuels.json'
        try:
            items = json.loads(catalogue.read_text(encoding='utf-8'))
            options = [discord.SelectOption(label=str(item['titre'])[:100], value=str(item['id'])) for item in items[:25]]
        except (OSError, ValueError, KeyError, TypeError):
            options = []
        if not options:
            options = [discord.SelectOption(label='Catalogue indisponible', value='missing')]
        super().__init__(placeholder='Choisir une réplique de NOX', options=options)

    async def callback(self, interaction):
        if interaction.user.id != self.view.owner_id or not interaction.guild or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Réservé à l’administrateur ayant ouvert ce panneau.', ephemeral=True)
        if not isinstance(interaction.channel, discord.TextChannel) or self.values[0] == 'missing':
            return await interaction.response.send_message('Salon ou catalogue indisponible.', ephemeral=True)
        cog = interaction.client.get_cog('NoxPublications')
        if cog is None:
            return await interaction.response.send_message('Module de publication indisponible.', ephemeral=True)
        await cog.noxpublier(interaction, app_commands.Choice(name=self.values[0], value=self.values[0]), interaction.channel)


class NoxManualView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(NoxManualSelect())


class NoxCentralAction(discord.ui.Button):
    def __init__(self, action, label, emoji, row=1, style=discord.ButtonStyle.secondary):
        super().__init__(label=label, emoji=emoji, style=style, row=row)
        self.action = action

    async def callback(self, interaction):
        view = self.view
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message('Ouvre ton propre centre avec `/nox`.', ephemeral=True)
        staff = self.action in ('planning', 'diagnostic', 'config', 'tv', 'adventure_start', 'adventure_end', 'mission_start', 'mission_end', 'presence', 'vie', 'evenements', 'surprise', 'roles_install', 'roles_sync', 'speak', 'manual')
        if staff and (not interaction.guild or not interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message('🛡️ Réservé aux administrateurs.', ephemeral=True)
        if self.action == 'cosmos':
            with connect() as con:
                c = creature(con, interaction.guild.id)
            await interaction.response.send_message(embed=creature_embed(c), view=NoxPanel(), ephemeral=True)
        elif self.action == 'refuge':
            from .nox_refuge import RefugeView
            await interaction.response.send_message('🏡 **Refuge de NOX** — Prends soin de NOX avec les boutons ci-dessous.', view=RefugeView(), ephemeral=True)
        elif self.action == 'tv':
            from .nox_tv import NoxTVDashboard
            await interaction.response.send_message('🎬 **NOX TV — Centre staff**', view=NoxTVDashboard(), ephemeral=True)
        elif self.action in ('planning', 'diagnostic'):
            cog_name = 'NoxPlanning' if self.action == 'planning' else 'NoxDiagnostics'
            cog = interaction.client.get_cog(cog_name)
            if cog is None:
                return await interaction.response.send_message('Module indisponible.', ephemeral=True)
            await getattr(cog, 'nox' + self.action)(interaction)
        elif self.action == 'config':
            await interaction.response.send_modal(NoxDailyConfigModal())
        elif self.action in ('presence', 'vie'):
            await interaction.response.send_modal(NoxActivityModal(self.action))
        elif self.action == 'evenements':
            await interaction.response.send_modal(NoxEventsModal())
        elif self.action == 'speak':
            await interaction.response.send_modal(NoxSpeakModal())
        elif self.action == 'manual':
            await interaction.response.send_message('📬 Choisis une réplique à publier dans ce salon.', view=NoxManualView(interaction.user.id), ephemeral=True)
        elif self.action == 'surprise':
            await interaction.response.send_message('🎭 Choisis une surprise. Elle sera publiée dans ce salon.', view=NoxSurpriseView(interaction.user.id), ephemeral=True)
        elif self.action == 'roles_sync':
            await interaction.response.send_modal(NoxRolesSyncModal())
        elif self.action == 'roles_install':
            cog = interaction.client.get_cog('NoxHonorRoles')
            if cog is None:
                return await interaction.response.send_message('Module de rôles indisponible.', ephemeral=True)
            choice = app_commands.Choice(name='Installer', value='installer')
            await cog.noxroles(interaction, choice, 0)
        elif self.action in ('adventure_start', 'adventure_end', 'mission_start', 'mission_end'):
            # Reuse existing business logic, including its DB guards and webhook sending.
            is_adventure = self.action.startswith('adventure')
            cog = interaction.client.get_cog('NoxAdventures' if is_adventure else 'NoxCosmicMissions')
            if cog is None:
                return await interaction.response.send_message('Module d’animation indisponible.', ephemeral=True)
            choice = app_commands.Choice(name='Lancer' if self.action.endswith('start') else 'Conclure',
                                         value='lancer' if self.action.endswith('start') else 'conclure')
            handler = cog.noxaventure if is_adventure else cog.noxmission
            await handler(interaction, choice, interaction.channel if self.action.endswith('start') else None)
        elif self.action == 'memoire':
            cog = interaction.client.get_cog('NoxMemory')
            if cog:
                await cog.noxmemoire(interaction)
            else:
                await interaction.response.send_message('Souvenirs indisponibles.', ephemeral=True)
        elif self.action == 'titres':
            cog = interaction.client.get_cog('NoxHonors')
            if cog:
                await cog.noxtitres(interaction)
            else:
                await interaction.response.send_message('Distinctions indisponibles.', ephemeral=True)
        elif self.action == 'animations':
            await interaction.response.send_message(
                '🎲 **Animations NOX**\n• Deux sondages quotidiens avec boutons de vote\n'
                '• Défi collectif à 15h50\n• Aventures et missions collectives\n'
                '• Bilan à 22h50\n\nLes participations se font sur les publications du salon.', ephemeral=True)
        elif self.action == 'publications':
            await interaction.response.send_message(
                '📬 **Publications NOX**\n12 créneaux de 10h00 à 22h50, dont 6 illustrés. '
                'Le planning et le diagnostic sont disponibles dans Administration.', ephemeral=True)


class NoxCentralView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.section = 'accueil'
        self.refresh()

    def refresh(self):
        self.clear_items()
        self.add_item(NoxCentralSelect())
        actions = {
            'accueil': [('cosmos','Univers','🌌'),('refuge','Refuge','🏡'),('animations','Animations','🎲')],
            'univers': [('cosmos','Ouvrir l’univers','🌌'),('refuge','Refuge','🏡')],
            'refuge': [('refuge','Ouvrir le Refuge','🏡'),('cosmos','Soins cosmiques','🌌'),('memoire','Mes souvenirs','📖'),('titres','Mes distinctions','🏅')],
            'animations': [('adventure_start','Lancer aventure','🚀'),('adventure_end','Clore aventure','🏁'),('mission_start','Lancer mission','🌟'),('mission_end','Clore mission','🏆'),('animations','Informations','🎲'),('surprise','Surprise','🎭')],
            'publications': [('publications','Programme','📬'),('manual','Publier une réplique','🗣️'),('speak','Faire parler NOX','✍️')],
            'tv': [('tv','Ouvrir NOX TV (staff)','🎬')],
            'administration': [('planning','Planning','📅'),('diagnostic','Diagnostic','🔎'),('config','Configurer le quotidien','⚙️'),('presence','Besoins de NOX','🏡'),('vie','Vie spontanée','💬'),('evenements','Événements','🎂'),('roles_install','Créer les rôles','🏅'),('roles_sync','Synchroniser rôles','🔄')],
        }
        # Discord limite chaque ligne à cinq boutons (largeur totale 5).
        # La ligne 0 est réservée au menu déroulant ; les actions sont
        # réparties sur les lignes 1 à 4, y compris en Administration.
        section_actions = actions[self.section]
        if len(section_actions) > 20:
            raise ValueError('Le panneau NOX ne peut afficher plus de 20 actions.')
        for index, (action, label, emoji) in enumerate(section_actions):
            self.add_item(NoxCentralAction(action, label, emoji, row=1 + index // 5))


class CosmicMissionClaim(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label='Récupérer ma récompense',emoji='🎁',style=discord.ButtonStyle.success)
    async def claim(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            msg=claim_mission(conn,i.guild.id,i.user.id,day)
        await i.response.send_message(msg,ephemeral=True)


class CosmicExplore(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(CosmicPlaceSelect())

class CosmicPlaceSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='🗺️ Choisir un lieu à visiter',min_values=1,max_values=1,
                         options=[discord.SelectOption(label=v[0][:100],value=k) for k,v in PLACES.items()])
    async def callback(self,i):
        with connect() as conn:
            ensure_world(conn,i.guild.id)
            msg=visit_place(conn,i.guild.id,i.user.id,self.values[0],datetime.now(LOCAL_TIMEZONE).date().isoformat())
        await i.response.send_message(msg,ephemeral=True)

class CosmicStoryButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    def __init__(self):
        super().__init__(timeout=None)
        # Bouton URL natif : redirige vers l'unique Refuge officiel de NOX.
        self.add_item(discord.ui.Button(
            label='Refuge de NOX', emoji='🐾', style=discord.ButtonStyle.link,
            url=f'https://discord.com/channels/{GUILD_ID}/1569826968659300392', row=0,
        ))
    @discord.ui.button(label='Explorer le monde',emoji='🗺️',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:story:world')
    async def world(self,i,b):
        with connect() as conn: text=map_text(conn,i.guild.id)
        await i.response.send_message('🗺️ **La carte cosmique**\n'+text,view=CosmicExplore(),ephemeral=True)
    @discord.ui.button(label='Mission du jour',emoji='🏅',style=discord.ButtonStyle.success,custom_id='cosmic:v101:story:mission')
    async def mission(self,i,b):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with connect() as conn:
            action,title,desc,done,claimed=mission_status(conn,i.guild.id,i.user.id,day)
        await i.response.send_message(f'🏅 **{title}**\n{desc}\n'+('🏆 Déjà récompensée' if claimed else '✅ Accomplie' if done else '⏳ À accomplir'),view=CosmicMissionClaim(),ephemeral=True)
    @discord.ui.button(label='État du cosmos',emoji='🔭',style=discord.ButtonStyle.secondary,custom_id='cosmic:v10:story:status')
    async def status(self,i,b):
        with connect() as conn: w=ensure_world(conn,i.guild.id)
        await i.response.send_message(embed=world_embed(w),ephemeral=True)

    @discord.ui.button(label='Portail secret',emoji='🔮',style=discord.ButtonStyle.secondary,custom_id='cosmic:v103:story:paradox')
    async def paradox(self,i,b):
        await show_paradox(i)

class ChaosCosmique(commands.Cog):
    cosmos = app_commands.Group(name='cosmos', description='🌌 Explorer le monde de Chaos Cosmique')

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.bot.add_view(CosmicChoices())
        self.bot.add_view(NoxPanel())
        self.bot.add_view(CosmicStoryButtons())
        self.cosmic_clock.start()

    def cog_unload(self):
        self.cosmic_clock.cancel()

    async def send_event(self, guild: discord.Guild, *, force=False):
        day = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        async with self._lock:
            with connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                world = tick_world(conn, guild.id, day)
                if not world['channel_id'] or world['paused']:
                    return 'L’univers est en pause ou aucun salon n’est configuré.'
                if world['active_event_id']:
                    return 'Une anomalie attend déjà une décision.'
                if not force and world['last_event_day'] == day:
                    return 'Une anomalie a déjà été publiée aujourd’hui.'
                channel_id = world['channel_id']
                previous = conn.execute('SELECT event_key FROM cosmic_events WHERE guild_id=? ORDER BY id DESC LIMIT 1', (guild.id,)).fetchone()
                choices = [e for e in EVENTS if not previous or e[0] != previous['event_key']]
                event = random.choice(choices)
                # Réservation en base avant publication : évite les doublons au redémarrage.
                try:
                    cur = conn.execute('INSERT INTO cosmic_events(guild_id,day,event_key) VALUES(?,?,?)',
                                       (guild.id, day, event[0]))
                except sqlite3.IntegrityError:
                    return 'Une anomalie existe déjà pour cette journée.'
                event_id = cur.lastrowid
                conn.execute('UPDATE cosmic_world SET last_event_day=? WHERE guild_id=?', (day, guild.id))
            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await guild.fetch_channel(channel_id)
                except (discord.HTTPException, discord.Forbidden):
                    channel = None
            if not isinstance(channel, discord.TextChannel):
                with connect() as conn:
                    conn.execute('DELETE FROM cosmic_events WHERE id=? AND message_id=0', (event_id,))
                    conn.execute('UPDATE cosmic_world SET last_event_day=? WHERE guild_id=?', ('', guild.id))
                return 'Salon introuvable ou incompatible : utilise un salon textuel.'
            try:
                msg = await channel.send(embed=event_embed(event), view=CosmicChoices(),
                                         allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.HTTPException) as exc:
                with connect() as conn:
                    conn.execute('DELETE FROM cosmic_events WHERE id=? AND message_id=0', (event_id,))
                    conn.execute('UPDATE cosmic_world SET last_event_day=? WHERE guild_id=?', ('', guild.id))
                log.warning('Publication cosmique impossible: %s', exc)
                return 'Publication impossible : vérifie les permissions du salon.'
            with connect() as conn:
                conn.execute('UPDATE cosmic_events SET message_id=? WHERE id=?', (msg.id, event_id))
                conn.execute('UPDATE cosmic_world SET active_event_id=? WHERE guild_id=?', (event_id, guild.id))
            return f'Anomalie publiée dans {channel.mention}.'

    @tasks.loop(minutes=60)
    async def cosmic_clock(self):
        for guild in self.bot.guilds:
            try:
                with connect() as conn:
                    world = ensure_world(conn, guild.id)
                    if world['paused'] or not world['channel_id']:
                        continue
                    before=world["last_tick"]
                    tick_world(conn, guild.id, datetime.now(LOCAL_TIMEZONE).date().isoformat())
                    resolve_due_echoes(conn,guild.id,datetime.now(LOCAL_TIMEZONE).date().isoformat())
                if before != datetime.now(LOCAL_TIMEZONE).date().isoformat():
                    await self.refresh_panel(guild)
                # Maximum une publication automatique par jour, après 18 h Paris.
                if datetime.now(LOCAL_TIMEZONE).hour >= 18:
                    await self.send_event(guild)
            except Exception:
                log.exception('Erreur horloge cosmique (serveur %s)', guild.id)

    @cosmic_clock.before_loop
    async def before_clock(self):
        await self.bot.wait_until_ready()

    @cosmos.command(name='observatoire', description='Voir les jauges et le monde de Chaos Cosmique')
    @app_commands.guild_only()
    async def observatoire(self, interaction: discord.Interaction):
        with connect() as conn:
            world = ensure_world(conn, interaction.guild.id)
        await interaction.response.send_message(embed=world_embed(world), ephemeral=True)

    @cosmos.command(name='explorer', description='Explorer le premier lieu du monde')
    @app_commands.guild_only()
    async def explorer(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            '🔭 **L’Observatoire**\nLes télescopes surveillent les failles du ciel. '
            'Une petite silhouette nommée Nox laisse parfois des miettes de comète.\n'
            '🗺️ Les autres lieux seront révélés dans les prochaines versions.', ephemeral=True)

    @cosmos.command(name='canal', description='Staff : choisir le salon des anomalies')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def canal(self, interaction: discord.Interaction, salon: discord.TextChannel):
        with connect() as conn:
            ensure_world(conn, interaction.guild.id)
            conn.execute('UPDATE cosmic_world SET channel_id=? WHERE guild_id=?', (salon.id, interaction.guild.id))
        await interaction.response.send_message(f'🌌 Salon cosmique configuré : {salon.mention}. '
                                                'L’univers reste en pause jusqu’à `/cosmos activer`.', ephemeral=True)

    @cosmos.command(name='activer', description='Staff : activer ou mettre en pause le monde')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def activer(self, interaction: discord.Interaction, actif: bool):
        with connect() as conn:
            world = ensure_world(conn, interaction.guild.id)
            if actif and not world['channel_id']:
                await interaction.response.send_message('Configure d’abord `/cosmos canal`.', ephemeral=True)
                return
            conn.execute('UPDATE cosmic_world SET paused=? WHERE guild_id=?', (0 if actif else 1, interaction.guild.id))
        await interaction.response.send_message('🌌 Univers activé.' if actif else '⏸️ Univers en pause.', ephemeral=True)

    @cosmos.command(name='declencher', description='Staff : publier une anomalie de test (maximum une par jour)')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def declencher(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await self.send_event(interaction.guild, force=True)
        await interaction.followup.send(result, ephemeral=True)


    @cosmos.command(name='installer', description='Staff : créer la catégorie et les salons de Chaos Cosmique')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def installer(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild=interaction.guild
        me=guild.me
        if not me or not me.guild_permissions.manage_channels:
            return await interaction.followup.send('Il me faut la permission **Gérer les salons**.', ephemeral=True)
        category=next((c for c in guild.categories if c.name in ('🌌 CHAOS COSMIQUE', '🌌・ＣＨＡＯＳ・ＣＯＳＭＩＱＵＥ')), None)
        channel_specs=[
            ('🔭・observatoire','🔭・𝓸𝓫𝓼𝓮𝓻𝓿𝓪𝓽𝓸𝓲𝓻𝓮'),
            ('🌀・anomalies','🌀・𝓪𝓷𝓸𝓶𝓪𝓵𝓲𝓮𝓼'),
            ('👾・nox','👾・𝓷𝓸𝔁'),
            ('📜・chroniques','📜・𝓬𝓱𝓻𝓸𝓷𝓲𝓺𝓾𝓮𝓼'),
            ('🗺️・exploration','🗺️・𝓮𝔁𝓹𝓵𝓸𝓻𝓪𝓽𝓲𝓸𝓷'),
            ('📖・histoire-du-chaos','📖・𝓱𝓲𝓼𝓽𝓸𝓲𝓻𝓮-𝓭𝓾-𝓬𝓱𝓪𝓸𝓼'),
        ]
        channels={}
        try:
            if category is None:
                category=await guild.create_category('🌌・ＣＨＡＯＳ・ＣＯＳＭＩＱＵＥ', reason='Installation de Chaos Cosmique')
            elif category.name != '🌌・ＣＨＡＯＳ・ＣＯＳＭＩＱＵＥ':
                await category.edit(name='🌌・ＣＨＡＯＳ・ＣＯＳＭＩＱＵＥ', reason='Harmonisation cosmique')
            for legacy, name in channel_specs:
                channel=next((c for c in category.text_channels if c.name in (legacy,name)),None)
                if channel is None:
                    channel=await guild.create_text_channel(name, category=category, reason='Installation Chaos Cosmique')
                elif channel.name != name:
                    await channel.edit(name=name, reason='Harmonisation des noms Chaos Cosmique')
                channels[legacy]=channel
            story_channel=channels['📖・histoire-du-chaos']
            # Permissions: lecture et réactions autorisées, écriture interdite aux membres.
            await story_channel.set_permissions(guild.default_role, view_channel=True, read_message_history=True,
                                                add_reactions=True, send_messages=False,
                                                create_public_threads=False, create_private_threads=False,
                                                send_messages_in_threads=False,
                                                reason='Salon de lecture seule pour l’histoire cosmique')
            await self.publish_story(story_channel)
        except (discord.Forbidden, discord.HTTPException, OSError) as exc:
            log.warning('Installation Cosmos: %s',exc)
            return await interaction.followup.send('Installation incomplète : vérifie les permissions Gérer les salons, Envoyer des messages et Joindre des fichiers.', ephemeral=True)
        with connect() as conn:
            ensure_world(conn,guild.id)
            creature(conn,guild.id)
            unlocks(conn,guild.id)
            conn.execute('UPDATE cosmic_world SET channel_id=? WHERE guild_id=?', (channels['🌀・anomalies'].id,guild.id))
            journal(conn,guild.id,'L’Observatoire ouvre ses portes.')
        await self.refresh_panel(guild, channels['🔭・observatoire'])
        await interaction.followup.send('🌌 Installation terminée : catégorie et six salons créés ou réutilisés, dont l’histoire en lecture seule. **Le monde reste en pause.** Active-le avec `/cosmos activer actif:True` lorsque tu es prêt.',ephemeral=True)

    async def publish_story(self, channel: discord.TextChannel):
        """Publie une seule présentation officielle; conserve les réactions existantes."""
        marker='CHAOS COSMIQUE · LE GRAND COMMENCEMENT'
        async for message in channel.history(limit=100):
            if message.author.id == self.bot.user.id and message.embeds and any(
                marker in (embed.footer.text or '') for embed in message.embeds
            ):
                old_message=message
                break
        else:
            old_message=None
        embed=horizons_embed(
            title='🌌 La légende du Chaos Cosmique',
            description=(
                '**Il était une fois… un univers qui avait oublié de lire son mode d’emploi.**\n\n'
                'Au commencement, il y eut une étoile. Puis une deuxième. Puis un stagiaire cosmique '
                'qui appuya sur un bouton marqué « SURTOUT PAS ». Ainsi naquit **HORIZONS**, '
                'un monde suspendu entre trois forces : **Énergie**, **Chaos** et **Harmonie**.\n\n'
                'Au sommet des îles flottantes se dressa **l’Observatoire**, chargé de surveiller '
                'les portes impossibles, les horloges syndiquées et les constellations fugueuses. '
                'Mais un matin, une petite boule de lumière éternua dans une nébuleuse… '
                'et **Nox** apparut. Personne ne sait s’il est né d’une étoile ou d’un biscuit oublié.\n\n'
                'Depuis, NOX accompagne les voyageurs dans leurs découvertes. Ses besoins et ses soins '
                'se trouvent dans son Refuge officiel, où chacun peut lui apporter de l’attention.\n\n'
                'Et comme si cela ne suffisait pas, **le Canard Suprême** a revendiqué la propriété '
                'de l’univers. Son premier décret ? « Chaque météorite doit porter un petit chapeau. » '
                'Le tribunal cosmique examine toujours sa demande.\n\n'
                'Des **anomalies** surgissent désormais : portes qui parlent, jardins d’étoiles, '
                'trains sans rails… Chaque choix peut transformer le monde et enrichir ses chroniques.\n\n'
                'Puis vinrent **Madame Paradoxe**, bibliothécaire des livres à venir, '
                '**Grille-Pain 3000**, prophète du petit-déjeuner, et **Professeur Gloups**, '
                'méduse astrophysicienne. Nox a désormais des envies, des habitudes et un humour imprévisible.\n\n'
                '✨ **Et maintenant, l’histoire attend ses nouveaux personnages : vous.**\n'
                'Explore les boutons ci-dessous, ou rejoins le **Refuge de NOX** pour prendre soin de lui. '
                'Les missions quotidiennes, les amitiés improbables et les archives secrètes t’attendent !'
            ),
            colour=discord.Colour.from_rgb(88, 90, 240),
        )
        embed.add_field(name='🐾 Le Refuge de NOX',value='Ses six besoins et ses soins se trouvent dans le **Refuge officiel**, accessible avec le bouton ci-dessous. Les anciennes jauges cosmiques ne sont plus utilisées pour les soins.',inline=False)
        embed.add_field(name='🗺️ Partir à l’aventure',value='**Explorer le monde** ouvre la carte et ses lieux ; **Mission du jour** propose un objectif ; **État du cosmos** décrit le monde ; **Portail secret** révèle ses mystères.',inline=False)
        embed.add_field(name='📜 Percer les secrets',value='Découvre les chroniques, les personnages improbables et les anomalies dans le serveur.',inline=False)
        embed.set_footer(text=marker)
        art=Path(__file__).resolve().parent.parent/'data'/'chaos_cosmique'/'histoire_chaos_cosmique.png'
        if old_message is not None:
            # Mise à jour sur place : les réactions restent et aucun doublon n'apparaît.
            if art.is_file():
                embed.set_image(url='attachment://histoire_chaos_cosmique.png')
                await old_message.edit(embed=embed,view=CosmicStoryButtons(),
                    attachments=[discord.File(art,filename='histoire_chaos_cosmique.png')])
            else:
                if old_message.attachments:
                    embed.set_image(url=old_message.attachments[0].url)
                await old_message.edit(embed=embed,view=CosmicStoryButtons())
            return False
        if art.is_file():
            embed.set_image(url='attachment://histoire_chaos_cosmique.png')
            await channel.send(embed=embed,view=CosmicStoryButtons(),file=discord.File(art,filename='histoire_chaos_cosmique.png'),
                               allowed_mentions=discord.AllowedMentions.none())
        else:
            await channel.send(embed=embed,view=CosmicStoryButtons(),allowed_mentions=discord.AllowedMentions.none())
        return True

    @cosmos.command(name='histoire', description='Staff : publier ou restaurer l’histoire officielle')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def histoire(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category=next((c for c in interaction.guild.categories if c.name in ('🌌 CHAOS COSMIQUE','🌌・ＣＨＡＯＳ・ＣＯＳＭＩＱＵＥ')),None)
        channel=next((c for c in category.text_channels if '𝓱𝓲𝓼𝓽𝓸𝓲𝓻𝓮' in c.name or 'histoire-du-chaos' in c.name),None) if category else None
        if channel is None:
            return await interaction.followup.send('Utilise d’abord `/cosmos installer` pour créer le salon.',ephemeral=True)
        created=await self.publish_story(channel)
        await interaction.followup.send('📖 Histoire publiée.' if created else '📖 Histoire actualisée avec ses boutons, sans doublon.',ephemeral=True)

    async def refresh_panel(self, guild, channel=None):
        with connect() as conn:
            world=ensure_world(conn,guild.id)
            creature(conn,guild.id)
            unlocks(conn,guild.id)
            row=conn.execute('SELECT * FROM cosmic_panels WHERE guild_id=?',(guild.id,)).fetchone()
            n=progress(conn,guild.id)
        if channel is None and row:
            channel=guild.get_channel(row['channel_id'])
        if channel is None:
            return
        embed=world_embed(world)
        embed.add_field(name='📜 Anomalies résolues',value=str(n),inline=False)
        embed.add_field(name='🗺️ Zones révélées',value=str(sum(n>=v[2] for v in PLACES.values())),inline=True)
        embed.add_field(name='⏯️ État',value='En pause' if world['paused'] else 'Éveillé',inline=True)
        if row and row['channel_id']==channel.id:
            try:
                message=await channel.fetch_message(row['message_id'])
                await message.edit(embed=embed)
                return
            except (discord.NotFound,discord.Forbidden,discord.HTTPException):
                pass
        try:
            message=await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden,discord.HTTPException):
            return
        with connect() as conn:
            conn.execute('INSERT OR REPLACE INTO cosmic_panels VALUES(?,?,?)',(guild.id,channel.id,message.id))

    @app_commands.command(name='nox', description='🐾 Centre interactif de NOX : communauté, activités et administration')
    @app_commands.guild_only()
    async def nox_dashboard(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=nox_dashboard_embed('accueil'),
            view=NoxCentralView(interaction.user.id), ephemeral=True)

    async def nox(self, interaction: discord.Interaction):
        with connect() as conn:
            c=creature(conn,interaction.guild.id)
        await interaction.response.send_message(embed=creature_embed(c),view=NoxPanel(),ephemeral=True)

    @cosmos.command(name='soigner', description='Prendre soin de Nox (une fois par jour et par action)')
    @app_commands.guild_only()
    @app_commands.choices(action=[app_commands.Choice(name='💙 Lui parler',value='parler'),app_commands.Choice(name='✨ Explorer avec lui',value='explorer'),app_commands.Choice(name='🍪 Lui offrir un biscuit imaginaire',value='nourrir'),app_commands.Choice(name='🧘 Méditer ensemble',value='mediter')])
    async def soigner(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        with connect() as conn:
            ok,message=care_nox(conn,interaction.guild.id,interaction.user.id,action.value,datetime.now(LOCAL_TIMEZONE).date().isoformat())
        await interaction.response.send_message(('👾 ' if ok else '⏳ ')+message,ephemeral=True)

    # Accessible depuis /nox → Carte du monde ; conservé comme méthode interne.
    async def carte(self, interaction: discord.Interaction):
        with connect() as conn:
            ensure_world(conn,interaction.guild.id)
            unlocks(conn,interaction.guild.id)
            n=progress(conn,interaction.guild.id)
        lines=[]
        for name, (label,desc,required) in PLACES.items():
            lines.append(f'**{label}** — {desc}' if n>=required else f'🔒 Zone inconnue · {required-n} anomalie(s) à résoudre')
        await interaction.response.send_message('🗺️ **Carte des Horizons**\n\n'+'\n'.join(lines),ephemeral=True)

    @cosmos.command(name='visiter', description='Explorer une zone débloquée')
    @app_commands.guild_only()
    @app_commands.choices(lieu=[app_commands.Choice(name=v[0],value=k) for k,v in PLACES.items()])
    async def visiter(self,interaction:discord.Interaction,lieu:app_commands.Choice[str]):
        with connect() as conn:
            ensure_world(conn,interaction.guild.id)
            n=progress(conn,interaction.guild.id)
            label,description,required=PLACES[lieu.value]
            if n<required:
                return await interaction.response.send_message(f'🔒 Ce lieu sera accessible après {required} anomalies résolues.',ephemeral=True)
            day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
            action='visiter:'+lieu.value
            if conn.execute('SELECT 1 FROM cosmic_actions WHERE guild_id=? AND user_id=? AND action=? AND day=?',
               (interaction.guild.id,interaction.user.id,action,day)).fetchone():
                return await interaction.response.send_message(f'{label}\n{description}\nTu as déjà fouillé ce lieu aujourd’hui.',ephemeral=True)
            conn.execute('INSERT INTO cosmic_actions VALUES(?,?,?,?)',(interaction.guild.id,interaction.user.id,action,day))
            item=random.choice(ARTIFACTS)
            conn.execute('INSERT INTO cosmic_inventory VALUES(?,?,?,1) ON CONFLICT(guild_id,user_id,item) DO UPDATE SET quantity=quantity+1',
               (interaction.guild.id,interaction.user.id,item))
        await interaction.response.send_message(f'{label}\n{description}\n✨ Tu trouves : **{item}** !',ephemeral=True)

    async def sac(self,interaction:discord.Interaction):
        with connect() as conn:
            rows=conn.execute('SELECT item,quantity FROM cosmic_inventory WHERE guild_id=? AND user_id=? AND quantity>0 ORDER BY item',
              (interaction.guild.id,interaction.user.id)).fetchall()
        await interaction.response.send_message('🎒 **Ton sac cosmique**\n'+('\n'.join(f'• {r["item"]} × {r["quantity"]}' for r in rows) if rows else 'Il est encore vide. Explore un lieu !'),ephemeral=True)

    async def chroniques(self,interaction:discord.Interaction):
        with connect() as conn:
            ensure_world(conn,interaction.guild.id)
            unlocks(conn,interaction.guild.id)
            rows=conn.execute('SELECT chapter FROM cosmic_chapters WHERE guild_id=? ORDER BY chapter',(interaction.guild.id,)).fetchall()
        lines=[f'**{i+1}. {CHAPTERS[i][0]}**\n{CHAPTERS[i][1]}' for i in [r['chapter'] for r in rows]]
        await interaction.response.send_message('📜 **Chroniques des Horizons**\n\n'+'\n\n'.join(lines),ephemeral=True)

    @cosmos.command(name='journal', description='Voir les dernières traces du monde')
    @app_commands.guild_only()
    async def lire_journal(self,interaction:discord.Interaction):
        with connect() as conn:
            rows=conn.execute('SELECT at,entry FROM cosmic_journal WHERE guild_id=? ORDER BY id DESC LIMIT 8',(interaction.guild.id,)).fetchall()
        lines=[f'• {r["at"][:10]} — {r["entry"]}' for r in rows]
        await interaction.response.send_message('📖 **Journal cosmique**\n'+('\n'.join(lines) if lines else 'Le monde attend sa première histoire.'),ephemeral=True)

    @cosmos.command(name='actualiser', description='Staff : mettre à jour le panneau de l’Observatoire')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def actualiser(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.refresh_panel(interaction.guild)
        await interaction.followup.send('🔭 Panneau actualisé, si le salon est accessible.',ephemeral=True)

    @cosmos.command(name='diagnostic', description='Staff : vérifier la configuration cosmique')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def diagnostic(self,interaction:discord.Interaction):
        with connect() as conn:
            w=ensure_world(conn,interaction.guild.id)
            c=creature(conn,interaction.guild.id)
            n=progress(conn,interaction.guild.id)
            panel=conn.execute('SELECT 1 FROM cosmic_panels WHERE guild_id=?',(interaction.guild.id,)).fetchone()
        await interaction.response.send_message(f'🌌 **Diagnostic Chaos Cosmique**\nActif : **{not bool(w["paused"])}** · Salon : **{w["channel_id"] or "non défini"}**\nAnomalies résolues : **{n}** · Active : **{w["active_event_id"]}**\nNox : **stade {c["stage"]}** · Panneau : **{bool(panel)}**\nBase : `chaos_cosmique.sqlite3`',ephemeral=True)


async def setup(bot):
    await bot.add_cog(ChaosCosmique(bot))
