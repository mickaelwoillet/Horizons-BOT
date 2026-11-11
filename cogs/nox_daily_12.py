"""Twelve daily NOX posts (Paris local time), opt-in, restart-safe and bounded."""
from __future__ import annotations
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR
from .nox_identity import send_as_nox
from .nox_refuge import DB
from . import nox_refuge_engine as engine

LOG = logging.getLogger(__name__)
PARIS = ZoneInfo('Europe/Paris')
CATALOG = Path(DATA_DIR) / 'nox' / 'dialogues_vie.json'
IMAGE_CATALOG = Path(DATA_DIR) / 'nox' / 'publications_illustrees.json'
IMAGE_DIR = Path(DATA_DIR) / 'nox_tv'
EXTRA_CATALOG = Path(DATA_DIR) / 'nox' / 'dialogues_participatifs.json'
# Six illustrated and six text-only appointments, each with a distinct editorial purpose.
SLOT_THEMES = (
    'humour', 'question', 'aventure', 'entraide', 'surprise', 'defi',
    'insolite', 'discussion', 'cosmos', 'bienveillance', 'tendresse', 'soir')
# Curated visual themes; every image belongs to one editorial slot.
IMAGE_THEMES = {
    'humour': ('humour',), 'aventure': ('aventure',),
    'surprise': ('surprise',), 'insolite': ('insolite',),
    'cosmos': ('cosmos',), 'tendresse': ('tendresse',),
}

TEXT_THEMES = {
    'question': ('question',),
    'entraide': ('entraide', 'vie_du_serveur'),
    'defi': ('defi',),
    'discussion': ('discussion', 'question'),
    'bienveillance': ('bienveillance',),
    'soir': ('soir', 'vie_du_serveur'),
}

# Six fixed illustrated slots per day, six text-only slots.
ILLUSTRATED_SLOTS = frozenset((0, 2, 4, 6, 8, 10))
# 12 evenly distributed slots; last at 22:50, all inside 10:00–23:00.
SLOTS = tuple((10 * 60 + 70 * i) for i in range(12))


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_config (
        guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 0)''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_posts (
        guild_id INTEGER NOT NULL, local_day TEXT NOT NULL, slot INTEGER NOT NULL,
        dialogue_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
        PRIMARY KEY(guild_id,local_day,slot))''')
    cols = {row[1] for row in con.execute('PRAGMA table_info(nox_daily_posts)')}
    if 'message_id' not in cols:
        con.execute('ALTER TABLE nox_daily_posts ADD COLUMN message_id INTEGER')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_illustrated_votes (
        guild_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, choice INTEGER NOT NULL,
        PRIMARY KEY(guild_id,message_id,user_id))''')
    con.commit()


def eligible_slot(local_dt):
    """No backfill: only publish within 15 minutes after each planned slot."""
    minute = local_dt.hour * 60 + local_dt.minute
    if minute >= 23 * 60:
        return None
    for i, planned in enumerate(SLOTS):
        if planned <= minute < planned + 15:
            return i
    return None


def choose_dialogue(dialogues, recent_ids, categories=None):
    if categories:
        matching = [d for d in dialogues if isinstance(d, dict) and d.get('categorie') in categories]
        if matching:
            dialogues = matching
    options = [d for d in dialogues if isinstance(d, dict) and
               isinstance(d.get('id'), str) and isinstance(d.get('texte'), str) and
               d['id'] not in recent_ids and 0 < len(d['texte']) <= 1800]
    if not options:
        options = [d for d in dialogues if isinstance(d, dict) and
                   isinstance(d.get('id'), str) and isinstance(d.get('texte'), str)
                   and 0 < len(d['texte']) <= 1800]
    return random.choice(options) if options else None


# Boutons persistants pour les six rendez-vous illustrés (webhook NOX).
# Les choix ne génèrent aucune poussière et ne créent pas de message public.
SCENE_REACTIONS = {
    'grillepain': ('🤝 Négocier', '🍞 Soutenir les tartines', '🚨 Appeler NOX'),
    'ascenseur': ('🕰️ Chercher aujourd’hui', '⏳ Voyager hier', '🚀 Visiter demain'),
}
DEFAULT_REACTIONS = ('💜 Encourager NOX', '✨ Participer', '😂 En rire')


def scene_reactions(scene_id):
    return SCENE_REACTIONS.get(scene_id, DEFAULT_REACTIONS)


class IllustratedReactionButton(discord.ui.Button):
    def __init__(self, choice):
        super().__init__(label=DEFAULT_REACTIONS[choice], style=discord.ButtonStyle.secondary,
                         custom_id=f'horizons:nox:illustre:{choice}')
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.message:
            await interaction.response.send_message('Cette interaction est réservée au serveur.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            initialize(con)
            row = con.execute('''SELECT local_day,dialogue_id FROM nox_daily_posts
                WHERE guild_id=? AND message_id=? AND state='sent' ''',
                (interaction.guild_id, interaction.message.id)).fetchone()
            if not row or not row['dialogue_id'].startswith('image:'):
                await interaction.response.send_message('Cette publication ne possède pas de vote actif.', ephemeral=True)
                return
            scene_id = row['dialogue_id'][6:]
            con.execute('''INSERT INTO nox_daily_illustrated_votes(guild_id,message_id,user_id,choice)
                VALUES(?,?,?,?) ON CONFLICT(guild_id,message_id,user_id)
                DO UPDATE SET choice=excluded.choice''',
                (interaction.guild_id, interaction.message.id, interaction.user.id, self.choice))
            con.commit()
            totals = [0, 0, 0]
            for choice, count in con.execute('''SELECT choice,COUNT(*) FROM nox_daily_illustrated_votes
                WHERE guild_id=? AND message_id=? GROUP BY choice''',
                (interaction.guild_id, interaction.message.id)):
                if 0 <= choice < 3:
                    totals[choice] = count
        label = scene_reactions(scene_id)[self.choice]
        await interaction.response.send_message(
            f'🐉 NOX a reçu ta réaction : **{label}** !\n'
            f'Votes : {totals[0]} · {totals[1]} · {totals[2]}. Tu peux changer ton choix.',
            ephemeral=True)


class IllustratedReactionView(discord.ui.View):
    def __init__(self, scene_id=None):
        super().__init__(timeout=None)
        labels = scene_reactions(scene_id)
        for index in range(3):
            button = IllustratedReactionButton(index)
            button.label = labels[index]
            self.add_item(button)


class NoxDaily12(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(IllustratedReactionView())
        self.daily_loop.start()

    def cog_unload(self):
        self.daily_loop.cancel()

    async def noxquotidien(self, interaction: discord.Interaction, salon: discord.TextChannel, actif: bool):
        if not interaction.guild or salon.guild.id != interaction.guild.id:
            await interaction.response.send_message('Salon invalide.', ephemeral=True)
            return
        me = interaction.guild.me
        perms = salon.permissions_for(me) if me else None
        if not perms or not (perms.manage_webhooks and perms.view_channel and perms.send_messages):
            await interaction.response.send_message('NOX a besoin de Voir le salon, Envoyer des messages et Gérer les webhooks.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            initialize(con)
            con.execute('''INSERT INTO nox_daily_config(guild_id,channel_id,enabled) VALUES(?,?,?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id,enabled=excluded.enabled''',
                (interaction.guild.id, salon.id, int(actif)))
            con.commit()
        await interaction.response.send_message(
            f'🐾 Publications NOX {"activées" if actif else "désactivées"} dans {salon.mention}. '
            '12 créneaux quotidiens de 10 h 00 à 22 h 50, heure de Paris. '
            'Aucun rattrapage massif après une coupure. '
            'Pense à désactiver `/noxvie` et `/noxpresence` si tu souhaites exactement 12 interventions automatiques.',
            ephemeral=True)

    @tasks.loop(minutes=1)
    async def daily_loop(self):
        local_now = datetime.now(PARIS)
        slot = eligible_slot(local_now)
        if slot is None:
            return
        # Pas de catalogue chargé si aucune publication quotidienne n'est activée.
        with engine.connect(DB) as con:
            initialize(con)
            rows = [dict(r) for r in con.execute(
                'SELECT * FROM nox_daily_config WHERE enabled=1')]
        if not rows:
            return
        day = local_now.date().isoformat()
        try:
            dialogues = json.loads(CATALOG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            LOG.exception('Catalogue NOX quotidien inaccessible')
            return
        if not isinstance(dialogues, list):
            return
        try:
            extra = json.loads(EXTRA_CATALOG.read_text(encoding='utf-8'))
            if isinstance(extra, list):
                dialogues.extend(extra)
        except (OSError, ValueError):
            LOG.exception('Catalogue participatif NOX inaccessible')
        try:
            image_scenes = json.loads(IMAGE_CATALOG.read_text(encoding='utf-8'))
            image_scenes = [scene for scene in image_scenes if
                isinstance(scene, dict) and isinstance(scene.get('id'), str)
                and isinstance(scene.get('texte'), str)
                and isinstance(scene.get('image'), str)
                and (IMAGE_DIR / Path(scene['image']).name).is_file()]
        except (OSError, ValueError):
            LOG.exception('Catalogue illustré NOX inaccessible')
            image_scenes = []
        for cfg in rows:
            guild_id = cfg['guild_id']
            with engine.connect(DB) as con:
                initialize(con)
                recent = {r[0] for r in con.execute('''SELECT dialogue_id FROM nox_daily_posts
                    WHERE guild_id=? AND state='sent' ORDER BY local_day DESC, slot DESC LIMIT 30''', (guild_id,))}
                theme = SLOT_THEMES[slot]
                illustrated = slot in ILLUSTRATED_SLOTS
                if illustrated:
                    # Editorial invariant: never replace a themed picture with an
                    # unrelated scene. Each catalogue entry binds its text and image.
                    themed = [scene for scene in image_scenes
                              if scene.get('theme') in IMAGE_THEMES.get(theme, ())]
                    unseen = [scene for scene in themed
                              if 'image:' + scene['id'] not in recent]
                    # Repeat only within the same theme when its catalogue is exhausted.
                    scene = random.choice(unseen or themed) if themed else None
                    item = ({'id': 'image:' + scene['id'], 'texte': scene['texte'],
                             'image': scene['image'], 'scene_id': scene['id']} if scene else None)
                elif slot == 5:
                    from .nox_daily_challenges import select_challenge
                    challenge = select_challenge(con, guild_id, day, slot)
                    item = ({'id': 'challenge:' + challenge['id'], 'texte': '🐾 Défi du jour de NOX !\n' + challenge['texte'] + '\n\nClique sur le bouton pour rejoindre le défi, et partage ta participation dans le salon si tu en as envie !'} if challenge else None)
                elif slot == 11:
                    from .nox_evening_recap import build_evening_recap
                    item = {'id': 'recap:' + day, 'texte': build_evening_recap(con, guild_id, day)}
                elif slot in (1, 7):
                    from .nox_daily_polls import select_poll
                    poll = select_poll(con, guild_id, day, slot)
                    item = ({'id': 'poll:' + poll['id'],
                             'texte': '🐾 Mini-sondage de NOX !\n' + poll['question'] +
                             '\n\n🅰️ ' + poll['choix'][0] +
                             '\n🅱️ ' + poll['choix'][1] +
                             '\n🇨 ' + poll['choix'][2] +
                             '\n\nVote avec les boutons ci-dessous !'} if poll else None)
                else:
                    item = choose_dialogue(dialogues, recent, TEXT_THEMES.get(theme))
                if item is None:
                    continue
                # Atomic reservation prevents double posting after concurrent loops/restarts.
                cur = con.execute('''INSERT OR IGNORE INTO nox_daily_posts
                    (guild_id,local_day,slot,dialogue_id,state) VALUES(?,?,?,?, 'pending')''',
                    (guild_id, day, slot, item['id']))
                con.commit()
                if not cur.rowcount:
                    continue
            # A missing channel is a known pre-send failure: release only this reservation.
            # HTTP failures after attempting a send remain reserved, since Discord may
            # have accepted the message despite a lost acknowledgement.
            def release_unsent_reservation():
                with engine.connect(DB) as cleanup_con:
                    cleanup_con.execute('''DELETE FROM nox_daily_posts
                        WHERE guild_id=? AND local_day=? AND slot=? AND state='pending' ''',
                        (guild_id, day, slot))
                    cleanup_con.commit()

            channel = self.bot.get_channel(cfg['channel_id'])
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(cfg['channel_id'])
                except (discord.HTTPException, discord.Forbidden):
                    LOG.warning('Salon NOX inaccessible: %s', cfg['channel_id'])
                    release_unsent_reservation()
                    continue
            if not isinstance(channel, discord.TextChannel):
                release_unsent_reservation()
                continue
            # Preflight a local attachment before any network send. Missing files are
            # deterministic pre-send failures, so the slot can retry safely.
            if item.get('image'):
                attachment = IMAGE_DIR / Path(item['image']).name
                if not attachment.is_file():
                    LOG.error('Illustration NOX manquante : %s', attachment)
                    release_unsent_reservation()
                    continue
            try:
                if item.get('image'):
                    # Pairing is fixed in the curated catalog: image and message cannot drift apart.
                    path = IMAGE_DIR / Path(item['image']).name
                    with path.open('rb') as fp:
                        sent_message = await send_as_nox(channel, content=item['texte'],
                                          file=discord.File(fp, filename=path.name),
                                          view=IllustratedReactionView(item['scene_id']))
                else:
                    if slot == 5:
                        from .nox_daily_challenges import ChallengeView
                        sent_message = await send_as_nox(channel, content=item['texte'], view=ChallengeView())
                    elif slot in (1, 7):
                        from .nox_daily_polls import PollView
                        sent_message = await send_as_nox(channel, content=item['texte'], view=PollView())
                    else:
                        sent_message = await send_as_nox(channel, content=item['texte'])
            except (discord.HTTPException, discord.Forbidden, OSError):
                LOG.exception('Publication quotidienne NOX impossible (guild=%s)', guild_id)
                # An error during/after sending can leave an ambiguous Discord result.
                # Keep the reservation rather than risk a duplicate publication.
                continue
            except Exception:
                LOG.exception('Erreur inattendue dans la publication NOX (guild=%s)', guild_id)
                # Isolate this guild/slot so one failure does not stop the daily task.
                continue
            # Persist delivery and interactive message IDs in a single transaction.
            # A database failure after a successful webhook send is ambiguous: retain
            # the pending reservation, never retry blindly and risk a duplicate.
            try:
                with engine.connect(DB) as con:
                    if sent_message is not None and slot == 5:
                        con.execute("""UPDATE nox_daily_challenges SET message_id=?
                            WHERE guild_id=? AND local_day=? AND slot=?""",
                            (sent_message.id, guild_id, day, slot))
                    if sent_message is not None and slot in (1, 7):
                        con.execute("""UPDATE nox_daily_polls SET message_id=?
                            WHERE guild_id=? AND local_day=? AND slot=?""",
                            (sent_message.id, guild_id, day, slot))
                    con.execute("""UPDATE nox_daily_posts SET state='sent',message_id=?
                        WHERE guild_id=? AND local_day=? AND slot=?""",
                        (sent_message.id if sent_message else None, guild_id, day, slot))
                    con.commit()
            except Exception:
                LOG.exception('NOX: envoi effectue mais enregistrement impossible (guild=%s, slot=%s)',
                              guild_id, slot)
                continue
            # Optional reply tracking must not prevent marking a post as sent.
            try:
                from .nox_interactions import record_post
                if sent_message is not None:
                    record_post(guild_id, channel.id, sent_message.id, day)
            except Exception:
                LOG.exception('Enregistrement de la publication NOX impossible')

    @daily_loop.before_loop
    async def before_daily_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NoxDaily12(bot))
