"""HORIZONS V9.0 — Chaos Cosmique, univers narratif autonome et optionnel."""
from __future__ import annotations

import asyncio
import logging
import random
import json
import sqlite3
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR, LOCAL_TIMEZONE

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
    embed = discord.Embed(title='🌌 Observatoire — Chaos Cosmique', color=0x5876E8,
        description=('Un univers fictif qui évolue au rythme des découvertes.\n'
                     '🔭 **Lieu découvert :** L’Observatoire\n'
                     '👾 **Nox :** une présence curieuse rôde dans les couloirs…'))
    embed.add_field(name='✨ Énergie', value=f"{world['energy']}/100")
    embed.add_field(name='🌀 Chaos', value=f"{world['chaos']}/100")
    embed.add_field(name='💙 Harmonie', value=f"{world['harmony']}/100")
    embed.set_footer(text='HORIZONS V9.0 · Univers narratif fictif · Sans conséquence sur les autres jeux')
    return embed


def event_embed(event, resolved=None):
    embed = discord.Embed(title=event[1], description=event[2], color=0x8860DA)
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
    e=discord.Embed(title=f"👾 {c['name']} — {stage}", color=0x657CEB,
       description=f"Tempérament : **{c['temperament']}**\nUne créature imaginaire qui grandit sans jamais mourir ni punir l’absence.")
    for label,key in [('Curiosité','curiosity'),('Affection','affection'),('Vitalité','vitality'),('Stabilité','stability')]:
        e.add_field(name=label, value=f"{'▰'*(c[key]//10)}{'▱'*(10-c[key]//10)} {c[key]}/100", inline=False)
    e.set_footer(text=f"Expérience : {c['xp']} · Stade {c['stage']}/4")
    return e

class ChaosCosmique(commands.Cog):
    cosmos = app_commands.Group(name='cosmos', description='🌌 Explorer le monde de Chaos Cosmique')

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.bot.add_view(CosmicChoices())
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
        category=discord.utils.get(guild.categories, name='🌌 CHAOS COSMIQUE')
        try:
            if category is None:
                category=await guild.create_category('🌌 CHAOS COSMIQUE', reason='Installation optionnelle de Chaos Cosmique')
            names=['🔭・observatoire', '🌀・anomalies', '👾・nox', '📜・chroniques', '🗺️・exploration']
            channels={}
            for name in names:
                channel=discord.utils.get(category.text_channels,name=name)
                if channel is None:
                    channel=await guild.create_text_channel(name, category=category, reason='Installation Chaos Cosmique')
                channels[name]=channel
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning('Installation Cosmos: %s',exc)
            return await interaction.followup.send('Création impossible : vérifie les permissions et les limites de salons.', ephemeral=True)
        with connect() as conn:
            ensure_world(conn,guild.id)
            creature(conn,guild.id)
            unlocks(conn,guild.id)
            conn.execute('UPDATE cosmic_world SET channel_id=? WHERE guild_id=?', (channels['🌀・anomalies'].id,guild.id))
            journal(conn,guild.id,'L’Observatoire ouvre ses portes.')
        await self.refresh_panel(guild, channels['🔭・observatoire'])
        await interaction.followup.send('🌌 Installation terminée : catégorie et cinq salons créés ou réutilisés. **Le monde reste en pause.** Active-le avec `/cosmos activer actif:True` lorsque tu es prêt.',ephemeral=True)

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

    @cosmos.command(name='nox', description='Rencontrer Nox, la créature de l’Observatoire')
    @app_commands.guild_only()
    async def nox(self, interaction: discord.Interaction):
        with connect() as conn:
            c=creature(conn,interaction.guild.id)
        await interaction.response.send_message(embed=creature_embed(c),ephemeral=True)

    @cosmos.command(name='soigner', description='Prendre soin de Nox (une fois par jour et par action)')
    @app_commands.guild_only()
    @app_commands.choices(action=[app_commands.Choice(name='💙 Lui parler',value='parler'),app_commands.Choice(name='✨ Explorer avec lui',value='explorer'),app_commands.Choice(name='🍪 Lui offrir un biscuit imaginaire',value='nourrir'),app_commands.Choice(name='🧘 Méditer ensemble',value='mediter')])
    async def soigner(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        day=datetime.now(LOCAL_TIMEZONE).date().isoformat()
        effects={'parler':('affection',9,'Nox raconte une histoire que même les étoiles trouvent exagérée.'),
                 'explorer':('curiosity',9,'Nox découvre un caillou. Il le nomme Directeur Général.'),
                 'nourrir':('vitality',9,'Nox dévore un biscuit imaginaire. Les miettes sont bien réelles.'),
                 'mediter':('stability',9,'Nox médite. Une chaise atteint l’illumination à sa place.')}
        with connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            c=creature(conn,interaction.guild.id)
            if conn.execute('SELECT 1 FROM cosmic_actions WHERE guild_id=? AND user_id=? AND action=? AND day=?',
              (interaction.guild.id,interaction.user.id,action.value,day)).fetchone():
                return await interaction.response.send_message('👾 Nox a déjà profité de cette activité avec toi aujourd’hui. Essaie une autre action !',ephemeral=True)
            conn.execute('INSERT INTO cosmic_actions VALUES(?,?,?,?)',(interaction.guild.id,interaction.user.id,action.value,day))
            field,delta,story=effects[action.value]
            conn.execute(f'UPDATE cosmic_creature SET {field}=MIN(100,{field}+?),xp=xp+5,last_care=? WHERE guild_id=?',
              (delta,day,interaction.guild.id))
            c=creature(conn,interaction.guild.id)
            stage=min(4,1+c['xp']//100)
            if stage>c['stage']:
                conn.execute('UPDATE cosmic_creature SET stage=?,last_evolution=? WHERE guild_id=?',
                  (stage,day,interaction.guild.id))
                story+=f' 🌟 **Métamorphose ! Nox atteint le stade {stage}.**'
                journal(conn,interaction.guild.id,f'Nox atteint le stade {stage}.')
        await interaction.response.send_message('👾 '+story,ephemeral=True)

    @cosmos.command(name='carte', description='Afficher les zones découvertes du monde')
    @app_commands.guild_only()
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

    @cosmos.command(name='sac', description='Consulter tes objets cosmiques')
    @app_commands.guild_only()
    async def sac(self,interaction:discord.Interaction):
        with connect() as conn:
            rows=conn.execute('SELECT item,quantity FROM cosmic_inventory WHERE guild_id=? AND user_id=? AND quantity>0 ORDER BY item',
              (interaction.guild.id,interaction.user.id)).fetchall()
        await interaction.response.send_message('🎒 **Ton sac cosmique**\n'+('\n'.join(f'• {r["item"]} × {r["quantity"]}' for r in rows) if rows else 'Il est encore vide. Explore un lieu !'),ephemeral=True)

    @cosmos.command(name='chroniques', description='Lire les fragments narratifs révélés')
    @app_commands.guild_only()
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
