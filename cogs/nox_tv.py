"""NOX TV — publications visuelles autonomes, opt-in et sans doublons."""
from __future__ import annotations
import json, random, sqlite3, logging, hashlib, os
from datetime import datetime, timedelta
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import DATA_DIR, LOCAL_TIMEZONE

LOG = logging.getLogger(__name__)
MEDIA = DATA_DIR / "nox_tv"
DB = DATA_DIR / "nox_tv.sqlite3"
COSMOS_DB = DATA_DIR / "chaos_cosmique.sqlite3"

# Salons du monde cosmique, personnalisables via .env.
CHANNEL_DEFAULTS = {
    'observatoire': 1569434249784729634,
    'anomalies': 1569434251785412699,
    'nox': 1569434252909608980,
    'chroniques': 1569434254448918701,
    'exploration': 1569434256311193721,
    'histoire': 1569440702167785522,
}
KIND_ROUTES = {
    'nox': 'nox',
    'canard': 'anomalies',
    'grille_pain': 'anomalies',
    'paradoxe': 'anomalies',
    'gloups': 'observatoire',
    'exploration': 'exploration',
    'chronique': 'chroniques',
}

def channel_for_kind(kind):
    destination = KIND_ROUTES.get(kind, 'observatoire')
    raw = os.getenv('COSMOS_CHANNEL_' + destination.upper(), str(CHANNEL_DEFAULTS[destination])).strip()
    return int(raw) if raw.isdecimal() and int(raw) > 0 else None

def chronicle_channel():
    return channel_for_kind('chronique')

def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db=sqlite3.connect(DB, timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("CREATE TABLE IF NOT EXISTS noxtv_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS noxtv_attempts (guild_id INTEGER NOT NULL, day TEXT NOT NULL, outcome TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(guild_id,day))")
    db.execute("CREATE TABLE IF NOT EXISTS noxtv_posts (guild_id INTEGER NOT NULL, day TEXT NOT NULL, visual_id TEXT NOT NULL, message_id INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,day))")
    db.execute("CREATE TABLE IF NOT EXISTS noxtv_votes (message_id INTEGER NOT NULL, user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, choice INTEGER NOT NULL, PRIMARY KEY(message_id,user_id))")
    db.execute("""CREATE TABLE IF NOT EXISTS noxtv_outcomes (
        message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL,
        winning_choice INTEGER NOT NULL, vote_count INTEGER NOT NULL,
        resolved_at TEXT NOT NULL, followup_sent INTEGER NOT NULL DEFAULT 0
    )""")
    db.execute("CREATE TABLE IF NOT EXISTS noxtv_manual_posts (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, visual_id TEXT NOT NULL, created_at TEXT NOT NULL)")
    # Migration non destructive : les anciens messages gardent leur canal de configuration.
    cols={r[1] for r in db.execute('PRAGMA table_info(noxtv_manual_posts)')}
    if 'channel_id' not in cols:
        db.execute('ALTER TABLE noxtv_manual_posts ADD COLUMN channel_id INTEGER NOT NULL DEFAULT 0')
    cols={r[1] for r in db.execute('PRAGMA table_info(noxtv_posts)')}
    if 'channel_id' not in cols:
        db.execute('ALTER TABLE noxtv_posts ADD COLUMN channel_id INTEGER NOT NULL DEFAULT 0')
    return db

CHOICES = ("🛡️ Défendre Nox", "🦆 Soutenir le canard", "🏃 Fuir discrètement")

class NoxTVChoices(discord.ui.View):
    """Persistent vote controls; one mutable vote per member and publication."""
    def __init__(self):
        super().__init__(timeout=None)

    async def cast(self, interaction: discord.Interaction, choice: int):
        if not interaction.guild_id or not interaction.message:
            await interaction.response.send_message("Cette action est réservée au serveur.", ephemeral=True)
            return
        with connect() as db:
            registered=db.execute('SELECT 1 FROM noxtv_posts WHERE message_id=? AND guild_id=? UNION SELECT 1 FROM noxtv_manual_posts WHERE message_id=? AND guild_id=?',(interaction.message.id,interaction.guild_id,interaction.message.id,interaction.guild_id)).fetchone()
            if not registered:
                await interaction.response.send_message('🎬 Ce message ne fait pas partie des scrutins NOX TV actifs.',ephemeral=True)
                return
            resolved=db.execute('SELECT 1 FROM noxtv_outcomes WHERE message_id=?',(interaction.message.id,)).fetchone()
            if resolved:
                await interaction.response.send_message('📜 Le scrutin est clos : la chronique est déjà écrite !',ephemeral=True)
                return
            previous = db.execute("SELECT choice FROM noxtv_votes WHERE message_id=? AND user_id=?", (interaction.message.id, interaction.user.id)).fetchone()
            db.execute("INSERT INTO noxtv_votes(message_id,user_id,guild_id,choice) VALUES(?,?,?,?) ON CONFLICT(message_id,user_id) DO UPDATE SET choice=excluded.choice", (interaction.message.id, interaction.user.id, interaction.guild_id, choice))
            rows = db.execute("SELECT choice, COUNT(*) AS total FROM noxtv_votes WHERE message_id=? GROUP BY choice", (interaction.message.id,)).fetchall()
        counts = {row['choice']: row['total'] for row in rows}
        summary = " · ".join(f"{CHOICES[n]} : {counts.get(n, 0)}" for n in range(3))
        change = "Vote modifié" if previous else "Vote enregistré"
        await interaction.response.send_message(f"✨ {change} ! **{CHOICES[choice]}**\n{summary}", ephemeral=True)

    @discord.ui.button(label="Défendre Nox", emoji="🛡️", style=discord.ButtonStyle.primary, custom_id="noxtv:vote:0")
    async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cast(interaction, 0)

    @discord.ui.button(label="Soutenir Coin-Coin", emoji="🦆", style=discord.ButtonStyle.secondary, custom_id="noxtv:vote:1")
    async def duck(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cast(interaction, 1)

    @discord.ui.button(label="Fuir", emoji="🏃", style=discord.ButtonStyle.success, custom_id="noxtv:vote:2")
    async def escape(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cast(interaction, 2)

OUTCOMES = (
    '🛡️ Le peuple protège Nox ! Le Canard Suprême doit déposer sa cuisse de poulet au vestiaire.',
    '🦆 Coin-Coin Ier triomphe ! Un décret exige désormais une autorisation royale pour les biscuits.',
    '🏃 Tout le monde prend la fuite. Grille-Pain 3000 se retrouve seul à présider la réunion.'
)


# Chaque univers reçoit une conclusion propre, sans recycler le même décret.
SCENE_VERDICTS = {
    'nox_biscuits_orbite': (
        'Nox reçoit une carte de citoyen honoraire de la planète Biscuit.',
        'Coin-Coin instaure une douane sur les pépites de chocolat.',
        'La planète Biscuit disparaît mystérieusement pendant le goûter.',
    ),
    'coincoin_couronne_rebelle': (
        'Nox négocie une pause pour la couronne et sauve la monarchie.',
        'Coin-Coin déclare la couronne coupable de haute trahison.',
        'La couronne s’envole et devient présidente de Saturne.',
    ),
    'paradoxe_reveil_infini': (
        'Nox obtient une sieste remboursée dans le passé.',
        'Coin-Coin impose un couvre-feu à toutes les horloges.',
        'Le réveil fuit dans une époque où personne ne dort.',
    ),
    'grille_pain_tartine_maire': (
        'Nox organise un débat public avec dégustation obligatoire.',
        'Coin-Coin conteste les résultats et réclame un recomptage des miettes.',
        'La tartine démissionne et ouvre une boulangerie spatiale.',
    ),
    'exploration_portail_chaussettes': (
        'L’équipe retrouve les chaussettes et les trie par constellation.',
        'Coin-Coin décrète une taxe sur les chaussettes orphelines.',
        'Le portail avale les chaussures et s’enfuit en courant.',
    ),
    'coincoin_conference_miettes': (
        '🛡️ Nox présente la preuve : Coin-Coin a des miettes jusque sous sa couronne.',
        '🦆 Coin-Coin interdit les photographies de miettes. Les biscuits portent plainte.',
        '🏃 La conférence se termine en course-poursuite entre journalistes et canards.',
    ),
    'paradoxe_ascenseur_temporel': (
        '⏳ Nox retrouve hier et récupère le goûter qu’il avait oublié.',
        '🦆 Coin-Coin impose un péage temporel. Demain refuse de payer.',
        '🏃 Tout le monde descend au mauvais siècle et rate le déjeuner.',
    ),
    'nox_sommeil_conseil': (
        '💤 Nox est élu président honoraire des siestes cosmiques.',
        '🦆 Coin-Coin interdit de ronfler en réunion. Il s’endort immédiatement.',
        '🏃 Le conseil évacue après un ronflement de magnitude sept.',
    ),
    'gloups_pluie_bulles': (
        '🫧 Nox transforme la pluie de bulles en festival de météo miniature.',
        '🦆 Coin-Coin revendique la propriété des nuages. Les bulles éclatent de rire.',
        '🏃 L’observatoire ouvre ses parapluies interdimensionnels.',
    ),
    'nox_jeu_ballon': (
        '🎲 Nox remporte le championnat de rebonds stellaires. Le ballon reçoit une médaille.',
        '🦆 Coin-Coin impose une taxe sur chaque rebond. Le ballon demande l’asile sur Saturne.',
        '🏃 Tout le monde fuit le gymnase. Le ballon continue de rebondir tout seul.'),
    'gloups_planete_fugueuse': (
        '🪐 Nox retrouve la planète et lui offre un hamac orbital. Crise résolue.',
        '🦆 Coin-Coin proclame la planète territoire royal. Elle déménage immédiatement.',
        '🏃 Le laboratoire est évacué. La planète fugueuse ouvre une agence de voyages.'),
    'grille_pain_panique_anime': (
        '🛡️ Nox sauve la tartine avec une couverture en chocolat. Le Conseil applaudit.',
        '🦆 Coin-Coin réquisitionne le grille-pain et proclame la loi martiale du petit-déjeuner.',
        '🏃 Les habitants évacuent. Grille-Pain 3000 se nomme ministre de la panique.'),
    'nox_faim': (
        '🍪 Les habitants organisent une collecte de biscuits pour Nox. Coin-Coin doit signer le reçu.',
        '🦆 Coin-Coin nationalise le garde-manger. Nox fonde aussitôt un syndicat des estomacs vides.',
        '🏃 Les témoins s’enfuient. Nox suit les miettes jusqu’au bureau du ministre des goûters.'),
    'nox_faim_pancarte': (
        '💙 Le comité de crise accorde à Nox trois biscuits et un câlin réglementaire.',
        '📜 Un décret royal interdit les pancartes affamées avant le petit déjeuner.',
        '🚀 Nox quitte la réunion avec sa pancarte et ouvre un restaurant sur la Lune.'),
    'nox_cookies': (
        '🍪 Les biscuits sont placés sous protection de Nox, qui les goûte tous par sécurité.',
        '👑 Coin-Coin proclame une taxe sur chaque pépite de chocolat. Révolte immédiate.',
        '💨 Les biscuits disparaissent pendant la fuite. Grille-Pain 3000 nie toute implication.'),
    'canard_attaque': (
        '🛡️ La garde de Nox confisque la cuisse de poulet et l’expose au musée des absurdités.',
        '🦆 Le Canard Suprême reçoit le titre de Maréchal de la Volaille Galactique.',
        '🏃 L’Observatoire est évacué. Le canard reste seul à donner des ordres aux étoiles.'),
    'course_du_canard': (
        '🛡️ Nox est acquitté : les miettes n’étaient pas des preuves recevables.',
        '👑 Coin-Coin remporte la course et réclame une médaille en forme de nugget.',
        '🏃 La poursuite finit dans un portail. Personne ne sait où est passée la cuisse de poulet.'),
    'grille_pain_apocalypse': (
        '🛡️ Nox débranche l’alarme. Le grille-pain est condamné à une semaine de tartines blondes.',
        '🦆 Coin-Coin nomme Grille-Pain 3000 ministre de la Défense des Croûtes.',
        '🏃 Tout le monde évacue la cuisine. La tartine brûlée devient une relique sacrée.'),
    'grille_pain_alerte': (
        '🛡️ Nox sauve la galaxie avec une tranche de pain frais et une serviette.',
        '🦆 Coin-Coin proclame une journée nationale du toast légèrement doré.',
        '🏃 Le personnel évacue le grille-pain. La tartine est promue cheffe de sécurité.'),
    'nox_conseil_panique': (
        '💙 Nox reçoit un oreiller officiel et la crise est ajournée pour cause de sieste.',
        '🦆 Coin-Coin tente de réveiller Nox et se fait nommer ministre du ronflement.',
        '🏃 Tous fuient le conseil. Nox signe le procès-verbal avec une empreinte de patte.'),
    'madame_paradoxe': (
        '⏳ Madame Paradoxe restitue le mardi disparu, mais conserve le goûter supplémentaire.',
        '🦆 Coin-Coin exige que le mardi supplémentaire soit rebaptisé Coincoindi.',
        '🏃 Tout le monde se cache mercredi. Le mardi supplémentaire les retrouve quand même.'),
    'paradoxe_mardi_25': (
        '⏳ Nox obtient le mardi 2,5 pour goûter. Le calendrier demande un arrêt maladie.',
        '🦆 Coin-Coin annexe ce jour supplémentaire et le baptise Canardedi.',
        '🏃 Tout le monde fuit le mardi 2,5. Il les rattrape le jeudi précédent.'),
    'gloups_experience_547': (
        '🧪 Nox libère la galaxie miniature. Elle lui laisse une étoile en souvenir.',
        '🦆 Coin-Coin invente la taxe intersidérale sur les éprouvettes.',
        '🏃 Les scientifiques s’échappent. La galaxie élit domicile dans une théière.'),
    'gloups_experience': (
        '🧪 Nox convainc Gloups de libérer la galaxie avant le dîner.',
        '🦆 Coin-Coin exige un brevet royal sur toutes les étoiles en bouteille.',
        '🏃 Les scientifiques fuient. La galaxie miniature s’installe dans la cafetière.'),
    'paradoxe_horloges_folles': (
        '⏳ Nox offre une pause goûter aux horloges. Le temps accepte de repartir.',
        '🦆 Coin-Coin instaure une taxe sur les secondes. Les minutes déposent un préavis de grève.',
        '🏃 Les habitants fuient dans demain. Madame Paradoxe les attend depuis hier.'),
    'gloups_fiole_rebelle': (
        '🧪 Nox négocie avec la galaxie. Elle obtient une fenêtre et deux jours de repos.',
        '🦆 Coin-Coin nomme la fiole ministre des Astres. Elle réclame aussitôt une augmentation.',
        '🏃 Tout le monde fuit le laboratoire. La galaxie miniature prend possession de la cafetière.'),
    'nox_etoile': (
        '🌟 Nox garde son étoile. Les habitants lui offrent une couverture de constellations.',
        '🦆 Coin-Coin tente de taxer les étoiles. Le ciel lui adresse une facture pour abus de pouvoir.',
        '🚀 Nox s’enfuit avec son étoile. Ils inventent une nouvelle constellation : le Biscuit Rieur.'),
    'canard_matraque_anime': (
        '🛡️ Nox convainc Coin-Coin de déposer sa cuisse de poulet au vestiaire des armes absurdes.',
        '🦆 Le Conseil reconnaît officiellement la cuisse de poulet comme sceptre royal. Les nuggets protestent.',
        '🏃 Le personnel se cache sous les bureaux. Coin-Coin déclare une victoire historique sur les meubles.'),
    'nox_dort_reunion': (
        '💙 Les habitants installent un oreiller royal pour Nox. La réunion est reportée à demain.',
        '🦆 Coin-Coin interdit les siestes pendant les conseils. Nox signe le décret en dormant.',
        '🏃 Les ministres s’éclipsent. Nox est élu président de séance à l’unanimité.'),
}

def verdict_for(visual_id, winner):
    """Narration propre à chaque scène, avec repli pour les visuels futurs."""
    if winner == -2:
        return '⚖️ Égalité cosmique ! Aucun camp ne l’emporte. Le Conseil ordonne une pause biscuits.'
    if winner not in (0, 1, 2):
        return '🌙 Aucun membre n’a voté. Le cosmos classe le dossier sans suite.'
    return SCENE_VERDICTS.get(visual_id, OUTCOMES)[winner]

def resolve_old_votes(db, guild_id, now):
    """Resolve posts from previous local days, exactly once, including ties deterministically."""
    today = now.date().isoformat()
    posts = db.execute("""SELECT p.message_id,p.day,p.visual_id FROM noxtv_posts p
        LEFT JOIN noxtv_outcomes o ON o.message_id=p.message_id
        WHERE p.guild_id=? AND p.day<? AND p.message_id>0 AND o.message_id IS NULL
        ORDER BY p.day ASC LIMIT 20""", (guild_id,today)).fetchall()
    new=[]
    for post in posts:
        counts = [0,0,0]
        for row in db.execute('SELECT choice,COUNT(*) n FROM noxtv_votes WHERE message_id=? AND guild_id=? GROUP BY choice',(post['message_id'],guild_id)):
            if row['choice'] in (0,1,2): counts[row['choice']]=row['n']
        total=sum(counts)
        # No votes means no arbitrary victory, mark resolved silently.
        winner = counts.index(max(counts)) if total and counts.count(max(counts)) == 1 else (-2 if total else -1)
        cur=db.execute('INSERT OR IGNORE INTO noxtv_outcomes(message_id,guild_id,winning_choice,vote_count,resolved_at) VALUES(?,?,?,?,?)',
            (post['message_id'],guild_id,winner,total,now.isoformat()))
        if cur.rowcount: new.append((post['message_id'],post['visual_id'],winner,total))
    manuals=db.execute("""SELECT m.message_id,m.visual_id FROM noxtv_manual_posts m
        LEFT JOIN noxtv_outcomes o ON o.message_id=m.message_id
        WHERE m.guild_id=? AND substr(m.created_at,1,10)<? AND o.message_id IS NULL
        ORDER BY m.created_at LIMIT 20""",(guild_id,today)).fetchall() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='noxtv_manual_posts'").fetchone() else []
    for post in manuals:
        counts=[0,0,0]
        for row in db.execute('SELECT choice,COUNT(*) n FROM noxtv_votes WHERE message_id=? AND guild_id=? GROUP BY choice',(post['message_id'],guild_id)):
            if row['choice'] in (0,1,2): counts[row['choice']]=row['n']
        total=sum(counts)
        winner=counts.index(max(counts)) if total and counts.count(max(counts)) == 1 else (-2 if total else -1)
        db.execute('INSERT OR IGNORE INTO noxtv_outcomes(message_id,guild_id,winning_choice,vote_count,resolved_at) VALUES(?,?,?,?,?)',
            (post['message_id'],guild_id,winner,total,now.isoformat()))
    return new

def nox_mood(guild_id):
    """Read existing Chaos Cosmique state, without creating or changing its tables."""
    if not COSMOS_DB.is_file():
        return 'normal'
    try:
        with sqlite3.connect(f'file:{COSMOS_DB}?mode=ro', uri=True, timeout=3) as db:
            db.row_factory = sqlite3.Row
            c = db.execute('SELECT vitality, affection, stability FROM cosmic_creature WHERE guild_id=?', (guild_id,)).fetchone()
            if c is None:
                return 'normal'
            if c['vitality'] <= 35:
                return 'fatigue'
            if c['affection'] <= 30:
                return 'calin'
            if c['stability'] <= 30:
                return 'panique'
    except (sqlite3.Error, OSError) as exc:
        LOG.debug('NOX TV: état cosmique indisponible: %s', exc)
    return 'normal'

def choose_visual(items, recent, mood, rng=None):
    """Prioritize a matching contextual scene, while avoiding the last two posts."""
    rng = rng or random
    pool = [x for x in items if x['id'] not in recent] or items
    contextual = [x for x in pool if mood in x.get('moods', [])]
    if contextual and rng.random() < 0.80:
        return rng.choice(contextual)
    return rng.choice(pool)

# Limite conservatrice pour les pièces jointes Discord (8 Mio).
MAX_MEDIA_BYTES = 8 * 1024 * 1024
ALLOWED_MEDIA_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

def safe_media_path(filename):
    """Reject traversal, symlinks outside media folder, missing or oversized assets."""
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        return None
    if Path(filename).suffix.lower() not in ALLOWED_MEDIA_SUFFIXES:
        return None
    root = MEDIA.resolve()
    asset = (MEDIA / filename).resolve()
    if asset.parent != root or not asset.is_file():
        return None
    try:
        if not 0 < asset.stat().st_size <= MAX_MEDIA_BYTES:
            return None
    except OSError:
        return None
    return asset

def catalogue():
    """Return only complete, unique, safely attachable catalogue entries."""
    try:
        entries = json.loads((MEDIA / 'catalogue.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        LOG.warning('NOX TV: catalogue illisible: %s', exc)
        return []
    if not isinstance(entries, list):
        return []
    valid, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get('id')
        if (not isinstance(key, str) or not key or key in seen
                or len(key) > 80 or not isinstance(entry.get('title'), str)
                or not isinstance(entry.get('text'), str)
                or entry.get('kind') not in KIND_ROUTES
                or safe_media_path(entry.get('file')) is None):
            continue
        seen.add(key)
        valid.append(entry)
    return valid

def audit_catalogue():
    """Read-only inventory of every scene, including rejected entries."""
    report = {'total': 0, 'valid': 0, 'rejected': [], 'routes': {}, 'animated': 0,
              'missing_verdicts': [], 'bytes': 0}
    try:
        entries = json.loads((MEDIA / 'catalogue.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        report['rejected'].append(f'catalogue illisible : {type(exc).__name__}')
        return report
    if not isinstance(entries, list):
        report['rejected'].append('racine JSON non liste')
        return report
    report['total'] = len(entries)
    seen = set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            report['rejected'].append(f'ligne {index} : entrée non objet')
            continue
        key = entry.get('id')
        filename = entry.get('file')
        asset = safe_media_path(filename)
        if (not isinstance(key, str) or not key or len(key) > 80 or key in seen
                or not isinstance(entry.get('title'), str)
                or not isinstance(entry.get('text'), str)
                or entry.get('kind') not in KIND_ROUTES or asset is None):
            report['rejected'].append(f'ligne {index} : {str(key)[:50]} invalide ou fichier absent')
            continue
        seen.add(key)
        report['valid'] += 1
        route = KIND_ROUTES[entry['kind']]
        report['routes'][route] = report['routes'].get(route, 0) + 1
        report['bytes'] += asset.stat().st_size
        if asset.suffix.lower() == '.gif':
            report['animated'] += 1
        if key not in SCENE_VERDICTS or len(SCENE_VERDICTS[key]) != 3:
            report['missing_verdicts'].append(key)
    return report

class NoxTV(commands.Cog):
    noxtv=app_commands.Group(name='noxtv', description='🎬 Publications visuelles de Nox (staff)')
    def __init__(self, bot):
        self.bot=bot
        self.bot.add_view(NoxTVChoices())
        self.clock.start()
    def cog_unload(self):
        self.clock.cancel()

    @staticmethod
    def _release_reservation(guild_id, day, manual):
        if not manual:
            with connect() as db:
                db.execute('DELETE FROM noxtv_posts WHERE guild_id=? AND day=? AND message_id=0',(guild_id,day))

    async def publish(self, guild, *, manual=False, channel_override=None, visual_id=None):
        now=datetime.now(LOCAL_TIMEZONE)
        day=now.date().isoformat()
        with connect() as db:
            setting=db.execute('SELECT * FROM noxtv_settings WHERE guild_id=?',(guild.id,)).fetchone()
            if not setting and not channel_override and not manual:
                return 'NOX TV non configuré.'
            if not manual and (not setting or not setting['enabled']):
                return 'NOX TV est désactivé.'
            channel_id=channel_override or (setting['channel_id'] if setting else None)
            if not manual and db.execute('SELECT 1 FROM noxtv_posts WHERE guild_id=? AND day=?',(guild.id,day)).fetchone():
                return 'Déjà publié aujourd’hui.'
            items=catalogue()
            if not items: return 'Aucun visuel disponible.'
            # Les aperçus/tests manuels ne changent jamais la rotation automatique.
            recent=[r['visual_id'] for r in db.execute('''
                SELECT visual_id FROM noxtv_posts
                WHERE guild_id=? AND message_id>0
                ORDER BY day DESC LIMIT 2''',(guild.id,))]
            choices=[x for x in items if x['id'] not in recent] or items
            if visual_id is not None:
                item=next((x for x in items if x['id'] == visual_id), None)
                if item is None:
                    return 'Visuel inconnu : consulte /noxtv catalogue.'
            else:
                item=choose_visual(choices, [], nox_mood(guild.id))
            if channel_override is None:
                channel_id=channel_for_kind(item.get('kind', 'observatoire'))
            if not channel_id:
                return 'Salon de destination non configuré.'
            if not manual:
                try:
                    db.execute('INSERT INTO noxtv_posts(guild_id,day,visual_id) VALUES(?,?,?)',(guild.id,day,item['id']))
                    db.commit()
                except sqlite3.IntegrityError:
                    return 'Publication déjà réservée aujourd’hui.'
        channel=guild.get_channel(channel_id)
        if channel is None:
            try: channel=await guild.fetch_channel(channel_id)
            except (discord.Forbidden,discord.HTTPException):
                self._release_reservation(guild.id, day, manual)
                return 'Salon introuvable.'
        if getattr(channel, 'guild', None) is None or channel.guild.id != guild.id:
            self._release_reservation(guild.id, day, manual)
            return 'Le salon ne fait pas partie de ce serveur.'
        if not isinstance(channel,discord.TextChannel):
            self._release_reservation(guild.id, day, manual)
            return 'Salon incompatible.'
        bot_member=guild.me
        perms=channel.permissions_for(bot_member) if bot_member else None
        if not (perms and perms.view_channel and perms.send_messages and perms.embed_links and perms.attach_files):
            self._release_reservation(guild.id, day, manual)
            return 'Permissions insuffisantes : voir, écrire, intégrer et joindre des fichiers.'
        asset=safe_media_path(item['file'])
        if asset is None:
            self._release_reservation(guild.id, day, manual)
            return 'Média manquant ou chemin non autorisé.'
        embed=discord.Embed(title=item['title'],description=item['text'],color=0x7764ff)
        embed.set_footer(text='NOX TV • Une catastrophe cosmique à la fois')
        embed.set_image(url='attachment://'+item['file'])
        try:
            msg=await channel.send(embed=embed,file=discord.File(asset,filename=item['file']),view=NoxTVChoices(),allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden,discord.HTTPException,OSError) as exc:
            LOG.warning('NOX TV: échec publication %s: %s',guild.id,exc)
            if not manual:
                with connect() as db:
                    db.execute('DELETE FROM noxtv_posts WHERE guild_id=? AND day=? AND message_id=0',(guild.id,day))
            return 'Publication impossible : vérifie les permissions.'
        with connect() as db:
            if manual:
                db.execute('INSERT OR IGNORE INTO noxtv_manual_posts(message_id,guild_id,visual_id,created_at,channel_id) VALUES(?,?,?,?,?)',(msg.id,guild.id,item['id'],now.isoformat(),channel.id))
            else:
                db.execute('UPDATE noxtv_posts SET message_id=?, channel_id=? WHERE guild_id=? AND day=?',(msg.id,channel.id,guild.id,day))
        return f'NOX TV : publication envoyée dans {channel.mention}.'

    async def close_ballots(self, guild, now):
        with connect() as db:
            resolve_old_votes(db,guild.id,now)
            new=[tuple(r) for r in db.execute("""SELECT o.message_id,p.visual_id,o.winning_choice,o.vote_count,
                    CASE WHEN p.channel_id>0 THEN p.channel_id ELSE s.channel_id END
                FROM noxtv_outcomes o JOIN noxtv_posts p ON p.message_id=o.message_id
                LEFT JOIN noxtv_settings s ON s.guild_id=o.guild_id
                WHERE o.guild_id=? AND o.followup_sent=0
                UNION ALL SELECT o.message_id,m.visual_id,o.winning_choice,o.vote_count,
                    CASE WHEN m.channel_id>0 THEN m.channel_id ELSE s.channel_id END
                FROM noxtv_outcomes o JOIN noxtv_manual_posts m ON m.message_id=o.message_id
                LEFT JOIN noxtv_settings s ON s.guild_id=o.guild_id
                WHERE o.guild_id=? AND o.followup_sent=0 LIMIT 20""",(guild.id,guild.id))]
        for message_id, visual_id, winner, count, channel_id in new:
            if not channel_id:
                continue
            destination_id=chronicle_channel()
            if not destination_id:
                LOG.warning("NOX TV: salon Chroniques non configuré pour le verdict %s", message_id)
                continue
            channel=guild.get_channel(destination_id)
            if channel is None:
                try:
                    channel=await guild.fetch_channel(destination_id)
                except (discord.Forbidden,discord.HTTPException):
                    continue
            if not isinstance(channel,discord.TextChannel) or channel.guild.id != guild.id:
                continue
            me=guild.me
            perms=channel.permissions_for(me) if me else None
            if not (perms and perms.view_channel and perms.send_messages and perms.embed_links):
                LOG.warning('NOX TV: impossible de publier le verdict dans %s', destination_id)
                continue
            embed=discord.Embed(title='📜 NOX TV · Le verdict du cosmos',
                description=f'**{count} vote(s)** pour la scène **{visual_id}**.\n\n{verdict_for(visual_id, winner)}',color=0x7764ff)
            try:
                # Un verdict publié dans Chroniques renvoie vers le message d'origine,
                # sans créer de référence Discord inter-salons invalide.
                source_url=f'https://discord.com/channels/{guild.id}/{channel_id}/{message_id}'
                embed.add_field(name='Publication originale', value=f'[Voir la scène et les votes]({source_url})', inline=False)
                await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden,discord.HTTPException) as exc:
                LOG.warning('NOX TV: verdict non envoyé %s: %s',message_id,exc)
            else:
                with connect() as db:
                    db.execute('UPDATE noxtv_outcomes SET followup_sent=1 WHERE message_id=?',(message_id,))

    @tasks.loop(minutes=60)
    async def clock(self):
        now=datetime.now(LOCAL_TIMEZONE)
        for guild in self.bot.guilds:
            try:
                await self.close_ballots(guild,now)
                if not 12 <= now.hour < 21: continue
                seed=f"{guild.id}:{now.date().isoformat()}:noxtv".encode()
                chance=int.from_bytes(hashlib.sha256(seed).digest()[:4],"big") / 2**32
                if chance < 0.15:
                    await self.publish(guild)
            except Exception:
                LOG.exception('NOX TV: erreur serveur %s',guild.id)
    @clock.before_loop
    async def ready(self):
        await self.bot.wait_until_ready()

    @noxtv.command(name='configurer',description='Choisir le salon des surprises visuelles')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def configurer(self,i:discord.Interaction,salon:discord.TextChannel):
        with connect() as db:
            db.execute('INSERT INTO noxtv_settings(guild_id,channel_id,enabled) VALUES(?,?,0) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id',(i.guild_id,salon.id))
        await i.response.send_message(f'🎬 Salon NOX TV : {salon.mention}. Publication automatique désactivée tant que tu ne l’actives pas.',ephemeral=True)

    @noxtv.command(name='activer',description='Activer ou arrêter les surprises automatiques')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def activer(self,i:discord.Interaction,actif:bool):
        with connect() as db:
            cur=db.execute('UPDATE noxtv_settings SET enabled=? WHERE guild_id=?',(int(actif),i.guild_id))
        await i.response.send_message('🎬 NOX TV '+('activé !' if actif else 'désactivé.') if cur.rowcount else 'Configure d’abord le salon avec /noxtv configurer.',ephemeral=True)

    @noxtv.command(name='statut',description='Voir la configuration, les visuels et l’humeur de Nox')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def statut(self,i:discord.Interaction):
        with connect() as db:
            setting=db.execute('SELECT * FROM noxtv_settings WHERE guild_id=?',(i.guild_id,)).fetchone()
            last=db.execute('SELECT day, visual_id FROM noxtv_posts WHERE guild_id=? ORDER BY day DESC LIMIT 1',(i.guild_id,)).fetchone()
        status=('🟢 Activé' if setting['enabled'] else '⚪ Désactivé') if setting else '⚪ Non configuré'
        salon=' · '.join(f'{k}: <#{channel_for_kind(k)}>' for k in ('nox','canard','gloups','exploration','chronique'))
        last_post=f"{last['day']} · {last['visual_id']}" if last else 'Aucune'
        await i.response.send_message(f"🎬 **NOX TV**\nÉtat : {status}\nSalon : {salon}\nVisuels disponibles : {len(catalogue())}\nHumeur détectée : {nox_mood(i.guild_id)}\nDernière publication : {last_post}",ephemeral=True)

    @noxtv.command(name='diagnostic', description='Contrôler les salons et permissions de NOX TV')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def diagnostic(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        if not i.guild:
            await i.followup.send('Commande réservée au serveur.', ephemeral=True)
            return
        lines=[]
        for key in ('nox', 'canard', 'paradoxe', 'gloups', 'exploration', 'chronique'):
            target_id=channel_for_kind(key)
            ch=i.guild.get_channel(target_id) if target_id else None
            if ch is None and target_id:
                try: ch=await i.guild.fetch_channel(target_id)
                except (discord.Forbidden, discord.HTTPException): pass
            if not isinstance(ch, discord.TextChannel) or ch.guild.id != i.guild.id:
                lines.append(f'❌ {key}: salon absent ou incompatible ({target_id or "non configuré"})')
                continue
            member=i.guild.me
            perms=ch.permissions_for(member) if member else None
            ok=bool(perms and perms.view_channel and perms.send_messages and perms.embed_links and perms.attach_files)
            lines.append(f'{"✅" if ok else "⚠️"} {key}: {ch.mention}'+('' if ok else ' — permissions insuffisantes (voir, écrire, intégrer, joindre)'))
        with connect() as db:
            setting=db.execute('SELECT enabled FROM noxtv_settings WHERE guild_id=?',(i.guild_id,)).fetchone()
        files=catalogue()
        lines.insert(0, f'Automatique : {"activé" if setting and setting["enabled"] else "désactivé"} · {len(files)} médias disponibles')
        await i.followup.send('🎬 **Diagnostic NOX TV**\n'+'\n'.join(lines),ephemeral=True)

    @noxtv.command(name='audit', description='Auditer les médias, les routes et les verdicts avant lancement')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def audit(self, i: discord.Interaction):
        report = audit_catalogue()
        route_lines = [f'• {name}: {count}' for name, count in sorted(report['routes'].items())]
        problems = report['rejected'] + [f'Verdict manquant : {key}' for key in report['missing_verdicts']]
        lines = [f"🎬 **Audit NOX TV** — {report['valid']}/{report['total']} scènes valides",
                 f"🎞️ {report['animated']} GIF · {report['bytes'] / (1024*1024):.1f} Mio de médias",
                 '**Répartition des salons :**', *route_lines,
                 '**Contrôles :** ' + ('✅ Aucun problème détecté' if not problems else f'⚠️ {len(problems)} anomalie(s)'),
                 *[f'❌ {problem}' for problem in problems[:12]]]
        if len(problems) > 12:
            lines.append(f'… et {len(problems) - 12} autres anomalies')
        await i.response.send_message('\n'.join(lines)[:1900], ephemeral=True)

    @noxtv.command(name='simulation', description='Simuler une scène sans rien publier')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def simulation(self, i: discord.Interaction):
        if not i.guild_id:
            await i.response.send_message('Commande réservée au serveur.', ephemeral=True)
            return
        entries = catalogue()
        if not entries:
            await i.response.send_message('🎬 Aucun média valide.', ephemeral=True)
            return
        with connect() as db:
            recent = [r['visual_id'] for r in db.execute(
                'SELECT visual_id FROM noxtv_posts WHERE guild_id=? AND message_id>0 ORDER BY day DESC LIMIT 2',
                (i.guild_id,))]
            setting = db.execute('SELECT enabled FROM noxtv_settings WHERE guild_id=?', (i.guild_id,)).fetchone()
        mood = nox_mood(i.guild_id)
        candidates = [entry for entry in entries if entry['id'] not in recent] or entries
        selected = choose_visual(candidates, [], mood, rng=random.Random())
        destination = channel_for_kind(selected.get('kind', 'observatoire'))
        enabled = bool(setting and setting['enabled'])
        channel = f'<#{destination}>' if destination else 'non configuré'
        lines = [
            '🎬 **Simulation NOX TV — aucune publication**',
            f'Automatique : {"activé" if enabled else "désactivé"}',
            f'Humeur de Nox : **{mood}**',
            f'Scène proposée : **{selected["title"]}** (`{selected["id"]}`)',
            f'Destination prévue : {channel}',
            f'Deux dernières scènes automatiques : {", ".join(recent) if recent else "aucune"}',
            'ℹ️ Simulation indicative : le prochain tirage réel peut être différent.',
        ]
        await i.response.send_message('\n'.join(lines), ephemeral=True)

    @noxtv.command(name='bilan', description='Bilan privé des scènes, votes et verdicts NOX TV')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bilan(self, i: discord.Interaction):
        if not i.guild_id:
            await i.response.send_message('Commande réservée au serveur.', ephemeral=True)
            return
        with connect() as db:
            auto = db.execute('SELECT COUNT(*) FROM noxtv_posts WHERE guild_id=? AND message_id>0', (i.guild_id,)).fetchone()[0]
            manual = db.execute('SELECT COUNT(*) FROM noxtv_manual_posts WHERE guild_id=?', (i.guild_id,)).fetchone()[0]
            votes = db.execute('SELECT COUNT(*) FROM noxtv_votes WHERE guild_id=?', (i.guild_id,)).fetchone()[0]
            voters = db.execute('SELECT COUNT(DISTINCT user_id) FROM noxtv_votes WHERE guild_id=?', (i.guild_id,)).fetchone()[0]
            outcomes = db.execute('SELECT COUNT(*) FROM noxtv_outcomes WHERE guild_id=?', (i.guild_id,)).fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM noxtv_outcomes WHERE guild_id=? AND followup_sent=0", (i.guild_id,)).fetchone()[0]
            top = db.execute("""SELECT p.visual_id, COUNT(*) AS n FROM noxtv_posts p
                WHERE p.guild_id=? AND p.message_id>0 GROUP BY p.visual_id ORDER BY n DESC, p.visual_id LIMIT 3""", (i.guild_id,)).fetchall()
            setting = db.execute('SELECT enabled FROM noxtv_settings WHERE guild_id=?', (i.guild_id,)).fetchone()
        top_text = ', '.join(f"`{row['visual_id']}` ({row['n']})" for row in top) or 'aucune'
        await i.response.send_message(
            '📊 **Bilan NOX TV — lecture seule**\n'
            f'Automatique : {"activé" if setting and setting["enabled"] else "désactivé"}\n'
            f'Publications automatiques : **{auto}**\n'
            f'Publications de test : **{manual}**\n'
            f'Votes actuellement enregistrés : **{votes}**, par **{voters}** membres distincts\n'
            f'Verdicts calculés : **{outcomes}** · chroniques en attente : **{pending}**\n'
            f'Scènes automatiques les plus publiées : {top_text}\n'
            'ℹ️ Les votes représentent les choix actuels, pas l’historique des changements de vote.',
            ephemeral=True)

    @noxtv.command(name='votes', description='Voir les résultats d’une publication NOX TV')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def votes(self, i:discord.Interaction, message_id:str):
        if not message_id.isdigit():
            await i.response.send_message('Identifiant de message invalide.',ephemeral=True)
            return
        with connect() as db:
            rows=db.execute('SELECT choice,COUNT(*) AS total FROM noxtv_votes WHERE guild_id=? AND message_id=? GROUP BY choice',(i.guild_id,int(message_id))).fetchall()
        counts={r['choice']:r['total'] for r in rows}
        await i.response.send_message('🎬 **Votes NOX TV**\n'+'\n'.join(f'{CHOICES[n]} : {counts.get(n,0)}' for n in range(3)),ephemeral=True)

    @noxtv.command(name='catalogue', description='Afficher les scènes disponibles et leur salon')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def voir_catalogue(self, i:discord.Interaction):
        entries=catalogue()
        lines=[f"`{x['id']}` → <#{channel_for_kind(x.get('kind', 'observatoire'))}>" for x in entries]
        await i.response.send_message('🎬 **Catalogue NOX TV**\n' + ('\n'.join(lines) if lines else 'Aucun média disponible.')[:1900],ephemeral=True)

    @noxtv.command(name='apercu', description='Prévisualiser une scène en privé, sans publication ni vote')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def apercu(self, i: discord.Interaction, scene: str):
        await i.response.defer(ephemeral=True)
        item=next((x for x in catalogue() if x['id']==scene),None)
        if item is None:
            await i.followup.send('Scène inconnue : utilise /noxtv catalogue.', ephemeral=True)
            return
        asset=safe_media_path(item['file'])
        if asset is None:
            await i.followup.send('Média manquant ou chemin non autorisé.', ephemeral=True)
            return
        embed=discord.Embed(title=item['title'],description=item['text'],color=0x7764ff)
        embed.set_image(url='attachment://'+item['file'])
        embed.set_footer(text='Prévisualisation privée · aucune publication ni vote')
        try:
            await i.followup.send(embed=embed,file=discord.File(asset,filename=item['file']),ephemeral=True)
        except (discord.Forbidden, discord.HTTPException, OSError) as exc:
            LOG.warning('NOX TV: aperçu impossible %s: %s', item['id'], exc)
            await i.followup.send('Impossible de transmettre cet aperçu. Vérifie la taille et le format du média.', ephemeral=True)

    @noxtv.command(name='tester' ,description='Publier une scène choisie sans toucher au calendrier')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tester(self,i:discord.Interaction, scene:str | None=None):
        await i.response.defer(ephemeral=True)
        if not i.guild:
            await i.followup.send('Commande réservée au serveur.', ephemeral=True)
            return
        await i.followup.send(await self.publish(i.guild,manual=True,visual_id=scene),ephemeral=True)

async def setup(bot):
    await bot.add_cog(NoxTV(bot))
