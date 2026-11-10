"""Le Regard du Jour : veille prudente, validation humaine, forum et reconnaissance."""
from __future__ import annotations
import asyncio
import logging
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse
import json
import hashlib
from contextlib import contextmanager
from urllib.parse import urlsplit
from cogs.horizons_arcade import award_xp, total_xp
from cogs.regard_editorial import (trusted_source, relevant_headline, news_date, within_recent_days,
    same_story, editorial_duplicate, followup_story, news_score, article_card, support_resources, normalize, meaningful_tokens, feed_excerpt)
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import DATA_DIR, GUILD_ID, STAFF_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID, MEMBER_ROLE_ID

logger = logging.getLogger(__name__)
TZ = ZoneInfo('Europe/Paris')
DB = DATA_DIR / 'regard_du_jour.sqlite3'
AGENDA_CAT = int(os.getenv('REGARD_AGENDA_CATEGORY_ID', '1566568994851524608'))
LOGS_CAT = int(os.getenv('REGARD_LOGS_CATEGORY_ID', '1566562045623799909'))
FORUM_ID = int(os.getenv('REGARD_FORUM_CHANNEL_ID', '0') or '0')
ARCHIVE_ID = int(os.getenv('REGARD_ARCHIVE_CHANNEL_ID', '0') or '0')
STAFF_CHANNEL_ID = int(os.getenv('REGARD_STAFF_CHANNEL_ID', '1566562235793416242'))
ENABLED = os.getenv('REGARD_ENABLED', 'false').strip().lower() in ('1','true','yes','oui')
XP_DAILY_LIMIT = max(3, min(30, int(os.getenv('REGARD_XP_DAILY_CAP', '15'))))
XP_COOLDOWN_SECONDS = max(30, int(os.getenv('REGARD_XP_COOLDOWN_SECONDS', '90')))
ARTICLE_MIN = max(1, min(5, int(os.getenv('REGARD_ARTICLES_MIN','3'))))
ARTICLE_MAX = max(ARTICLE_MIN, min(5, int(os.getenv('REGARD_ARTICLES_MAX','5'))))
PUBLISH_HOUR = max(0, min(23, int(os.getenv('REGARD_PUBLISH_HOUR','18'))))
WEEKLY_RECAP_ENABLED = os.getenv('REGARD_WEEKLY_RECAP_ENABLED','true').lower() in ('true','1','oui','yes')
WEEKLY_RECAP_HOUR = max(PUBLISH_HOUR, min(23, int(os.getenv('REGARD_WEEKLY_RECAP_HOUR','18'))))
WEEKLY_RECAP_MINUTE = max(0, min(59, int(os.getenv('REGARD_WEEKLY_RECAP_MINUTE','30'))))
TRUSTED_EXTRA = frozenset(x.strip().lower() for x in os.getenv('REGARD_ADDITIONAL_TRUSTED_DOMAINS','').split(',') if x.strip())
AUTO_MODE = os.getenv('REGARD_AUTO_MODE', 'true').lower() in ('1','true','yes','oui')
MUSIC_NEW_RELEASE_DAYS = max(1, min(90, int(os.getenv('REGARD_MUSIC_NEW_RELEASE_DAYS', '14'))))
MUSIC_REPEAT_DAYS = max(7, int(os.getenv('REGARD_MUSIC_REPEAT_DAYS', '90')))
MUSIC_AUTO_DISCOVERY = os.getenv('REGARD_MUSIC_AUTO_DISCOVERY', 'false').lower() in ('1','true','yes','oui')
WEEKLY_VOTE_ENABLED = os.getenv('REGARD_WEEKLY_VOTE_ENABLED', 'true').lower() in ('1','true','yes','oui')
WEEKLY_VOTE_HOUR = max(0, min(23, int(os.getenv('REGARD_WEEKLY_VOTE_HOUR', '19'))))
# Titres choisis pour leur message explicite; la plateforme de musique confirme les liens,
# pas le sens des paroles. Une nouvelle sortie non vérifiée n'est jamais présentée comme engagée.
MUSIC_CATALOG = [
 ('Same Love', 'Macklemore Ryan Lewis Mary Lambert'),
 ('Born This Way', 'Lady Gaga'),
 ('True Colors', 'Cyndi Lauper'),
 ('Imagine', 'John Lennon'),
 ('Tout le monde', 'Zazie'),
 ('Black or White', 'Michael Jackson'),
 ('Respect', 'Aretha Franklin'),
 ('People Have the Power', 'Patti Smith'),
]

TOPICS = [
    ('Discriminations', 'racisme discrimination France justice'),
    ('LGBTQIA+', 'homophobie transphobie France justice'),
    ('Antisémitisme et religions', 'antisémitisme islamophobie discrimination religieuse France'),
    ('Solidarité', 'association lutte discriminations inclusion solidarité France'),
]

@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS regard_items (
       id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, title TEXT NOT NULL,
       url TEXT NOT NULL UNIQUE, category TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
       created_at TEXT NOT NULL, reviewed_by INTEGER);
    CREATE TABLE IF NOT EXISTS regard_posts (
       day TEXT PRIMARY KEY, thread_id INTEGER NOT NULL, published_at TEXT NOT NULL,
       archived_at TEXT);
    CREATE TABLE IF NOT EXISTS regard_xp (
       guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, day TEXT NOT NULL,
       points INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,user_id,day));
    CREATE TABLE IF NOT EXISTS regard_xp_messages (
       message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS regard_music (day TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL, url TEXT NOT NULL, selected_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS regard_weekly_polls (week_start TEXT PRIMARY KEY, thread_id INTEGER NOT NULL, created_at TEXT NOT NULL, closed_at TEXT);
    CREATE TABLE IF NOT EXISTS regard_weekly_votes (week_start TEXT NOT NULL, user_id INTEGER NOT NULL, choice INTEGER NOT NULL, voted_at TEXT NOT NULL, PRIMARY KEY(week_start,user_id));
    CREATE TABLE IF NOT EXISTS regard_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS regard_thread_parts (day TEXT NOT NULL, part_key TEXT NOT NULL, message_id INTEGER NOT NULL,
       PRIMARY KEY(day,part_key));
    CREATE TABLE IF NOT EXISTS regard_proposals (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
       user_id INTEGER NOT NULL, url TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, title TEXT NOT NULL,
       status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, reviewed_by INTEGER);
    CREATE TABLE IF NOT EXISTS regard_weekly_digests (week_start TEXT PRIMARY KEY,
       thread_id INTEGER NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS regard_weekly_songs (week_start TEXT NOT NULL, position INTEGER NOT NULL, day TEXT NOT NULL,
       title TEXT NOT NULL, artist TEXT NOT NULL, url TEXT NOT NULL, PRIMARY KEY(week_start,position));
    CREATE TABLE IF NOT EXISTS regard_xp_audit (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL,
       user_id INTEGER NOT NULL, day TEXT NOT NULL, fingerprint TEXT NOT NULL, awarded_at TEXT NOT NULL,
       points INTEGER NOT NULL);
    ''')
    # Migrations additives : conservent les données des anciennes versions.
    existing={row['name'] for row in conn.execute('PRAGMA table_info(regard_items)').fetchall()}
    for name,typ in [('source','TEXT'),('source_url','TEXT'),('published_at','TEXT'),('summary','TEXT')]:
        if name not in existing: conn.execute(f'ALTER TABLE regard_items ADD COLUMN {name} {typ}')
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def staff(member):
    return isinstance(member, discord.Member) and (member.guild_permissions.manage_guild or any(r.id in (STAFF_ROLE_ID,ADMIN_ROLE_ID,MOD_ROLE_ID) for r in member.roles))

def shorten(s, n=180):
    return re.sub(r'\s+', ' ', s).strip()[:n]

class RegardDuJour(commands.Cog):
    regard = app_commands.Group(name="regard", description="Le Regard du Jour : articles, votes et bilans")
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()
        self.regeneration_lock = asyncio.Lock()
        with connect() as c: pass
        self.scheduler.start()

    def cog_unload(self):
        self.scheduler.cancel()

    def guild(self):
        return self.bot.get_guild(GUILD_ID) if GUILD_ID else next(iter(self.bot.guilds), None)

    async def channels(self, create=False):
        guild = self.guild()
        if not guild: return None, None
        forum = guild.get_channel(FORUM_ID) if FORUM_ID else discord.utils.get(guild.channels, name='🌍・𝗹𝗲-𝗿𝗲𝗴𝗮𝗿𝗱-𝗱𝘂-𝗷𝗼𝘂𝗿')
        archive = guild.get_channel(ARCHIVE_ID) if ARCHIVE_ID else discord.utils.get(guild.channels, name='🗃️・𝗮𝗿𝗰𝗵𝗶𝘃𝗲𝘀-𝗱𝘂-𝗿𝗲𝗴𝗮𝗿𝗱')
        if create:
            agenda, logs = guild.get_channel(AGENDA_CAT), guild.get_channel(LOGS_CAT)
            if not isinstance(agenda, discord.CategoryChannel) or not isinstance(logs, discord.CategoryChannel):
                raise RuntimeError('Catégories Agenda/Journaux techniques introuvables.')
            if forum is None:
                forum = await guild.create_forum(name='🌍・𝗹𝗲-𝗿𝗲𝗴𝗮𝗿𝗱-𝗱𝘂-𝗷𝗼𝘂𝗿', category=agenda,
                    topic='Actualités françaises sur les discriminations, initiatives solidaires et musique inclusive. Discussions respectueuses.',
                    reason='Installation demandée du Regard du Jour HORIZONS')
            if archive is None:
                archive = await guild.create_text_channel(name='🗃️・𝗮𝗿𝗰𝗵𝗶𝘃𝗲𝘀-𝗱𝘂-𝗿𝗲𝗴𝗮𝗿𝗱', category=logs,
                    topic='Journal technique des publications du Regard du Jour archivées.',
                    reason='Journal technique du Regard du Jour HORIZONS')
        return forum if isinstance(forum, discord.ForumChannel) else None, archive if isinstance(archive, discord.TextChannel) else None

    async def collect(self, day):
        """Collecte des flux RSS avec statistiques de rejet exploitables en console.

        Une source et une date doivent être identifiables. Aucun article n'est
        inventé ; les titres ne sont pas présentés comme des faits vérifiés.
        """
        inserted = 0
        today = datetime.fromisoformat(day).date()
        timeout = aiohttp.ClientTimeout(total=25)
        stats = {'received': 0, 'bad_link': 0, 'untrusted': 0,
                 'old': 0, 'irrelevant': 0, 'duplicates': 0, 'errors': 0}
        async with aiohttp.ClientSession(timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; HORIZONS/1.0; community news digest)'}) as session:
            for category, query in TOPICS:
                url = 'https://news.google.com/rss/search?q=' + quote(query + ' when:7d') + '&hl=fr&gl=FR&ceid=FR:fr'
                category_count = 0
                try:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        raw = await response.read()
                    root = ET.fromstring(raw)
                    entries = root.findall('.//channel/item')
                    logger.info('Regard RSS %s : %d entrées reçues', category, len(entries))
                    for item in entries:
                        stats['received'] += 1
                        title = shorten(item.findtext('title') or '', 230)
                        link = (item.findtext('link') or '').strip()
                        source_node = item.find('source')
                        source = (source_node.text or '').strip() if source_node is not None else ''
                        source_url = source_node.attrib.get('url', '') if source_node is not None else ''
                        published = news_date(item.findtext('pubDate') or '')
                        excerpt = feed_excerpt(item.findtext('description') or '', title)
                        if len(title) < 18 or not link.startswith('https://news.google.com/'):
                            stats['bad_link'] += 1; continue
                        if not source or not trusted_source(source_url, TRUSTED_EXTRA):
                            stats['untrusted'] += 1; continue
                        if not within_recent_days(published, today, max_days=7):
                            stats['old'] += 1; continue
                        if not relevant_headline(title, category):
                            stats['irrelevant'] += 1; continue
                        with connect() as db:
                            cur = db.execute("""INSERT OR IGNORE INTO regard_items
                                (day,title,url,category,status,created_at,source,source_url,published_at,summary)
                                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                (day,title,link,category,'pending',datetime.now(TZ).isoformat(),
                                 source,source_url,published.isoformat(),excerpt))
                            if cur.rowcount: inserted += 1; category_count += 1
                            else: stats['duplicates'] += 1
                        if category_count >= 12: break
                except (aiohttp.ClientError, asyncio.TimeoutError, ET.ParseError, ValueError) as exc:
                    stats['errors'] += 1
                    logger.warning('Regard RSS %s : %s : %s', category, type(exc).__name__, exc)
        logger.info('Regard collecte %s : nouveaux=%d, stats=%s', day, inserted, stats)
        with connect() as db:
            db.execute('INSERT OR REPLACE INTO regard_state(key,value) VALUES(?,?)',
                       ('diagnostic:'+day, str({'new':inserted, **stats})))
        return inserted

    def auto_select(self, day):
        """Classement transparent, sans inventer de faits ni doublons sur 30 jours."""
        with connect() as db:
            rows=db.execute("SELECT * FROM regard_items WHERE day=? AND status='pending' ORDER BY id",(day,)).fetchall()
            approved=db.execute("SELECT title FROM regard_items WHERE day=? AND status='approved' AND category!='🎵 Musique'",(day,)).fetchall()
            history=db.execute("SELECT title FROM regard_items WHERE day>=? AND day<? AND status='approved'",((datetime.fromisoformat(day).date()-timedelta(days=30)).isoformat(),day)).fetchall()
            prev_titles=[r['title'] for r in history]
            chosen_titles=[r['title'] for r in approved]
            categories={r['category'] for r in db.execute("SELECT category FROM regard_items WHERE day=? AND status='approved'",(day,)).fetchall()}
            candidates=[]
            for r in rows:
                title=r['title']
                if not relevant_headline(title,r['category']): continue
                if any(editorial_duplicate(title,p) for p in chosen_titles+prev_titles): continue
                score=news_score(title,r['category'],r['published_at'] or '')
                if score<1: continue
                candidates.append((score,r))
            candidates.sort(key=lambda x:(-x[0],x[1]['id']))
            selected=[]
            for _,r in candidates:
                if len(selected)+len(approved)>=ARTICLE_MAX: break
                if r['category'] in categories: continue
                if any(editorial_duplicate(r['title'],chosen) for chosen in chosen_titles):continue
                selected.append(r); chosen_titles.append(r['title']);categories.add(r['category'])
            for _,r in candidates:
                if len(selected)+len(approved)>=ARTICLE_MAX:break
                if r in selected or any(editorial_duplicate(r['title'],chosen) for chosen in chosen_titles):continue
                selected.append(r);chosen_titles.append(r['title'])
            for r in selected:
                db.execute("UPDATE regard_items SET status='approved' WHERE id=? AND status='pending'",(r['id'],))
            return len(selected)

    async def discover_music(self, day, session):
        """Recherche de nouveautés via le catalogue public iTunes FR.

        Un titre évocateur n'est PAS une preuve du sens des paroles. Les résultats
        restent présentés comme pistes thématiques, jamais comme hymnes vérifiés.
        """
        if not MUSIC_AUTO_DISCOVERY:
            return None
        date = datetime.fromisoformat(day).date()
        themes = ('acceptance', 'equality', 'solidarity', 'diversity', 'tolerance',
                  'égalité', 'tolérance', 'solidarité', 'différence', 'acceptation',
                  'pride', 'together', 'inclusion', 'respect')
        candidates = []
        for term in themes:
            try:
                async with session.get('https://itunes.apple.com/search', params={
                    'term':term, 'entity':'song', 'country':'FR', 'limit':40,
                    'explicit':'No'}) as response:
                    response.raise_for_status()
                    payload=await response.json(content_type=None)
                for song in payload.get('results', []):
                    title=str(song.get('trackName') or '').strip()
                    artist=str(song.get('artistName') or '').strip()
                    url=str(song.get('trackViewUrl') or '')
                    released=str(song.get('releaseDate') or '')[:10]
                    if not (title and artist and url.startswith('https://music.apple.com/') and released):
                        continue
                    try: age=(date-datetime.fromisoformat(released).date()).days
                    except ValueError: continue
                    if not 0 <= age <= MUSIC_NEW_RELEASE_DAYS: continue
                    normalized=re.sub(r'[^a-zà-ÿ0-9 ]+', ' ', title.casefold())
                    if not any(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',normalized) for t in themes):
                        continue
                    candidates.append((age,title,artist,url,released))
            except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
                logger.warning('Recherche nouveautés iTunes (%s) : %s',term,exc)
        # Tri stable : nouveauté la plus récente d'abord, puis titre et artiste.
        for age,title,artist,url,released in sorted(set(candidates)):
            if not self.music_recently_used(title,artist,day):
                return {'title':title,'artist':artist,'url':url,'released':released,
                        'description':'Nouveauté repérée par son titre ; message à découvrir et à discuter, sans interprétation automatique des paroles.'}
        return None

    def music_recently_used(self, title, artist, day):
        threshold=(datetime.fromisoformat(day).date()-timedelta(days=MUSIC_REPEAT_DAYS)).isoformat()
        with connect() as db:
            rows=db.execute('SELECT title,artist FROM regard_music WHERE day>=? AND day<?',(threshold,day)).fetchall()
        return any(title.casefold()==r['title'].casefold() and artist.casefold()==r['artist'].casefold() for r in rows)

    async def select_music(self, day):
        """Nouveautés vérifiables puis catalogue éditorial, sans répétition 90 jours."""
        with connect() as db:
            old=db.execute('SELECT title,artist,url FROM regard_music WHERE day=?',(day,)).fetchone()
            if old: return dict(old)
        # Les propositions musicales validées par le staff sont prioritaires.
        # Une source externe proposée n'est jamais lue/exécutée par le bot.
        with connect() as db:
            suggestions=db.execute("SELECT title,url FROM regard_items WHERE category='🎵 Musique' AND status='approved' AND day<=? AND day>=? ORDER BY id DESC LIMIT 20",
                (day,(datetime.fromisoformat(day).date()-timedelta(days=14)).isoformat())).fetchall()
        for proposal in suggestions:
            title=proposal['title']; artist='Sélection validée par le staff'
            if self.music_recently_used(title,artist,day):continue
            with connect() as db:
                db.execute('INSERT OR IGNORE INTO regard_music(day,title,artist,url,selected_at) VALUES(?,?,?,?,?)',
                    (day,title,artist,proposal['url'],datetime.now(TZ).isoformat()))
            return {'title':title,'artist':artist,'url':proposal['url'],
                'description':'🎧 Découverte proposée par la communauté et sélectionnée par le staff.'}
        timeout=aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout,headers={'User-Agent':'HORIZONS/1.0'}) as session:
            candidate=await self.discover_music(day,session)
            if candidate:
                with connect() as db:
                    db.execute('INSERT OR IGNORE INTO regard_music(day,title,artist,url,selected_at) VALUES(?,?,?,?,?)',
                        (day,candidate['title'],candidate['artist'],candidate['url'],datetime.now(TZ).isoformat()))
                return candidate
            start=int(hashlib.sha256(day.encode()).hexdigest()[:8],16)%len(MUSIC_CATALOG)
            for shift in range(len(MUSIC_CATALOG)):
                title,artist=MUSIC_CATALOG[(start+shift)%len(MUSIC_CATALOG)]
                if self.music_recently_used(title,artist,day): continue
                try:
                    async with session.get('https://itunes.apple.com/search',params={
                        'term':f'{title} {artist}','entity':'song','country':'FR','limit':15}) as response:
                        response.raise_for_status()
                        payload=await response.json(content_type=None)
                    for song in payload.get('results',[]):
                        actual_title=str(song.get('trackName',''))
                        actual_artist=str(song.get('artistName',''))
                        link=str(song.get('trackViewUrl',''))
                        if (normalize(title) == normalize(actual_title) and
                            normalize(artist.split()[0]) in normalize(actual_artist) and
                            link.startswith('https://') and
                            not self.music_recently_used(actual_title,actual_artist,day)):
                            with connect() as db:
                                db.execute('INSERT OR IGNORE INTO regard_music(day,title,artist,url,selected_at) VALUES(?,?,?,?,?)',
                                    (day,actual_title,actual_artist,link,datetime.now(TZ).isoformat()))
                            return {'title':actual_title,'artist':actual_artist,'url':link,
                                    'description':'Redécouverte : un titre du répertoire éditorial HORIZONS.'}
                except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
                    logger.warning('Recherche musicale indisponible: %s',exc)
        return None

    async def notify_staff(self, message):
        guild=self.guild()
        channel=guild.get_channel(STAFF_CHANNEL_ID) if guild else None
        if isinstance(channel, discord.TextChannel):
            try: await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException: logger.exception('Notification staff Regard du Jour')

    def followup_link(self, item, day):
        """Rapprochement conservateur avec les anciens sujets, jamais une preuve de lien."""
        cutoff=(datetime.fromisoformat(day).date()-timedelta(days=60)).isoformat()
        with connect() as db:
            rows=db.execute("""SELECT i.title,p.thread_id FROM regard_items i
                JOIN regard_posts p ON p.day=i.day WHERE i.day>=? AND i.day<?
                AND i.status='approved' ORDER BY i.day DESC LIMIT 100""",(cutoff,day)).fetchall()
        for past in rows:
            if followup_story(item['title'],past['title']):
                return f'https://discord.com/channels/{GUILD_ID}/{past["thread_id"]}'
        return ''

    async def ensure_post_parts(self, day, thread, items, music):
        """Reprise après interruption : les éléments déjà envoyés ne sont pas repostés."""
        with connect() as db:
            done={r['part_key'] for r in db.execute('SELECT part_key FROM regard_thread_parts WHERE day=?',(day,)).fetchall()}
        parts=[]
        for i,item in enumerate(items,1):
            parts.append((f'article:{item["id"]}',f'**{i:02d} · À la une**\n'+article_card(item,self.followup_link(item,day))))
        positive=next((r for r in items if r['category']=='Solidarité'),None)
        if positive:
            parts.append(('lueur',f'☀️ **La Lueur du Jour**\nUne initiative positive repérée dans la sélection : **{discord.utils.escape_markdown(positive["title"]) }**\n{positive["url"]}'))
        else:
            parts.append(('lueur','☀️ **La Lueur du Jour**\nAucune initiative positive suffisamment vérifiée dans les flux du jour. Partage une bonne nouvelle sourcée si tu en connais une 💙'))
        if music:
            parts.append(('music',f'🎵 **La Note d’HORIZONS**\n**{discord.utils.escape_markdown(music["title"])} — {discord.utils.escape_markdown(music["artist"])}**\n🎧 {music["url"]}\n{music.get("description", "Une découverte à discuter.")}'))
        else:
            parts.append(('music','🎵 **La Note d’HORIZONS** : aucun lien musical fiable disponible aujourd’hui.'))
        parts.append(('resources',support_resources()))
        parts.append(('question','💬 **La question du jour**\nQuelle information t’a fait réfléchir ? Comment agir avec respect et solidarité ?\nRéponds directement à l’article qui t’intéresse pour garder le fil lisible.'))
        for key,content in parts:
            if key in done:continue
            msg=await thread.send(content[:1950],allowed_mentions=discord.AllowedMentions.none(),suppress_embeds=True)
            with connect() as db:
                db.execute('INSERT OR IGNORE INTO regard_thread_parts(day,part_key,message_id) VALUES(?,?,?)',(day,key,msg.id))

    async def update_daily_index(self, day, thread, items):
        """Sommaire cliquable vers chaque article : une seule édition du premier message."""
        with connect() as db:
            state=db.execute('SELECT 1 FROM regard_state WHERE key=?',('index:'+day,)).fetchone()
            # Le sommaire peut évoluer après une collecte de rattrapage.
            refs={r['part_key']:r['message_id'] for r in db.execute('SELECT part_key,message_id FROM regard_thread_parts WHERE day=?',(day,)).fetchall()}
        if any(f'article:{r["id"]}' not in refs for r in items):return
        links=[]
        for idx,r in enumerate(items,1):
            msg_id=refs[f'article:{r["id"]}']
            links.append(f'**{idx:02d}.** {shorten(r["title"],85)} — https://discord.com/channels/{GUILD_ID}/{thread.id}/{msg_id}')
        if not links:links=['Aucun article récent n’a pu être suffisamment vérifié aujourd’hui.']
        try:
            message=await thread.fetch_message(thread.id)
            if '📌 **Sommaire interactif**' not in message.content:
                content=(message.content+'\n\n📌 **Sommaire interactif**\n'+'\n'.join(links))[:1950]
                await message.edit(content=content,allowed_mentions=discord.AllowedMentions.none())
            with connect() as db:db.execute('INSERT OR IGNORE INTO regard_state(key,value) VALUES(?,?)',('index:'+day,'done'))
        except discord.HTTPException:
            logger.warning('Sommaire quotidien impossible pour %s ; une reprise aura lieu au prochain passage.',day)

    async def publish(self, day, *, rebuild=False):
        forum,_=await self.channels()
        if forum is None: raise RuntimeError('Forum absent : utilise /regard_installer ou configure son ID.')
        async with self.lock:
            with connect() as db:
                old=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(day,)).fetchone()
                items=db.execute("SELECT * FROM regard_items WHERE day=? AND status='approved' AND category!='🎵 Musique' ORDER BY id LIMIT ?",(day,ARTICLE_MAX)).fetchall()
            if not items and not old:
                logger.warning('Regard %s : aucune actualité validée ; publication vide annulée.', day)
                return 'Aucune actualité vérifiée : publication reportée. Consulte /regard_diagnostic.'
            music=await self.select_music(day) if AUTO_MODE else None
            if rebuild:
                old = None
            if not old and not rebuild:
                # Après un crash entre la création Discord et l'enregistrement SQLite,
                # récupérer le sujet existant au lieu d'en ouvrir un deuxième.
                title='🌍 Le Regard du Jour — '+datetime.fromisoformat(day).strftime('%d/%m/%Y')
                existing=next((t for t in forum.threads if t.name==title and t.owner_id==self.bot.user.id),None)
                if existing is None:
                    try:
                        async for previous in forum.archived_threads(limit=80):
                            if previous.name==title and previous.owner_id==self.bot.user.id:
                                existing=previous;break
                    except (discord.HTTPException,discord.Forbidden):
                        logger.warning('Recherche des sujets archivés impossible, contrôle des doublons incomplet')
                if existing:
                    with connect() as db:
                        db.execute('INSERT OR IGNORE INTO regard_posts(day,thread_id,published_at) VALUES(?,?,?)',
                            (day,existing.id,datetime.now(TZ).isoformat()))
                    old={'thread_id':existing.id}
            if not old:
                headline=('🌍 **Le Regard du Jour — '+datetime.fromisoformat(day).strftime('%d/%m/%Y')+'**\n'
                     '📰 Actualités françaises · ☀️ La Lueur du Jour · 🎵 La Note d’HORIZONS\n\n'
                     f'**{len(items)} article(s) sourcé(s)** sélectionné(s) aujourd’hui.'
                     + (' Moins de 3 articles ont passé les vérifications : aucune information ne sera inventée.' if len(items)<ARTICLE_MIN else '')
                     + '\nLes titres sont attribués aux médias, ils ne constituent pas des conclusions judiciaires. '
                     'Pour chaque sujet, utilise la fonction **Répondre** du message correspondant.\n'
                     '⚠️ Certains articles peuvent évoquer des violences ou des discriminations.')
                result=await forum.create_thread(name='🌍 Le Regard du Jour — '+datetime.fromisoformat(day).strftime('%d/%m/%Y'),
                    content=headline,auto_archive_duration=10080,reason='Veille quotidienne HORIZONS',
                    allowed_mentions=discord.AllowedMentions.none())
                thread=result.thread
                with connect() as db:
                    if rebuild:
                        db.execute('INSERT OR REPLACE INTO regard_posts(day,thread_id,published_at,archived_at) VALUES(?,?,?,NULL)',
                            (day,thread.id,datetime.now(TZ).isoformat()))
                    else:
                        db.execute('INSERT OR IGNORE INTO regard_posts(day,thread_id,published_at) VALUES(?,?,?)',
                            (day,thread.id,datetime.now(TZ).isoformat()))
            else:
                thread=forum.get_thread(old['thread_id']) or self.bot.get_channel(old['thread_id'])
                if thread is None:thread=await self.bot.fetch_channel(old['thread_id'])
                if not isinstance(thread,discord.Thread):raise RuntimeError('Sujet quotidien introuvable sur Discord.')
                if thread.archived:
                    await thread.edit(archived=False,reason='Reprise d’une publication interrompue')
            await self.ensure_post_parts(day,thread,items,music)
            await self.update_daily_index(day,thread,items)
            return f'Publié ou vérifié : {thread.mention}'

    def week_start(self, date):
        return (date - timedelta(days=date.weekday())).isoformat()

    def ensure_weekly_song_snapshot(self, week):
        """Compatibilité : conserver les votes créés par une version antérieure."""
        with connect() as db:
            current=db.execute('SELECT COUNT(*) FROM regard_weekly_songs WHERE week_start=?',(week,)).fetchone()[0]
            if current:return
            old=db.execute('SELECT 1 FROM regard_weekly_polls WHERE week_start=?',(week,)).fetchone()
            if not old:return
            songs=db.execute('SELECT day,title,artist,url FROM regard_music WHERE day>=? AND day<? ORDER BY day',
                (week,(datetime.fromisoformat(week).date()+timedelta(days=7)).isoformat())).fetchall()
            for pos,song in enumerate(songs,1):
                db.execute('INSERT OR IGNORE INTO regard_weekly_songs(week_start,position,day,title,artist,url) VALUES(?,?,?,?,?,?)',
                    (week,pos,song['day'],song['title'],song['artist'],song['url']))

    async def close_weekly_poll(self, week):
        """Annonce le résultat d'un vote terminé, une seule fois, même après redémarrage."""
        self.ensure_weekly_song_snapshot(week)
        with connect() as db:
            poll=db.execute('SELECT thread_id,closed_at FROM regard_weekly_polls WHERE week_start=?',(week,)).fetchone()
            if not poll or poll['closed_at']: return
            songs=db.execute('SELECT day,title,artist,url FROM regard_weekly_songs WHERE week_start=? ORDER BY position',(week,)).fetchall()
            scores=db.execute('SELECT choice,COUNT(*) AS votes FROM regard_weekly_votes WHERE week_start=? GROUP BY choice ORDER BY votes DESC,choice ASC',(week,)).fetchall()
        thread=self.bot.get_channel(poll['thread_id'])
        if thread is None:
            try: thread=await self.bot.fetch_channel(poll['thread_id'])
            except discord.HTTPException: return
        if not isinstance(thread,discord.Thread): return
        if thread.archived:await thread.edit(archived=False,reason='Résultat de la Voix de la Semaine')
        if scores and 1<=scores[0]['choice']<=len(songs):
            song=songs[scores[0]['choice']-1]
            msg=f"🏆 **La Voix de la Semaine** : **{discord.utils.escape_markdown(song['title'])}** — {discord.utils.escape_markdown(song['artist'])} !\n{scores[0]['votes']} vote(s) · {song['url']}\nMerci à toutes et tous pour vos découvertes 💙"
        else:
            msg='🎵 Le vote de cette semaine est terminé. Aucun suffrage enregistré : pas de gagnant cette fois-ci. 💙'
        await thread.send(msg,allowed_mentions=discord.AllowedMentions.none())
        with connect() as db: db.execute('UPDATE regard_weekly_polls SET closed_at=? WHERE week_start=? AND closed_at IS NULL',(datetime.now(TZ).isoformat(),week))
        try: await thread.edit(archived=True,locked=True,reason='Fin du vote musical hebdomadaire')
        except discord.HTTPException: logger.warning('Impossible de verrouiller le vote %s',week)

    async def publish_weekly_poll(self, today):
        """Dimanche 19h : vote sur les chansons effectivement publiées cette semaine."""
        forum,_=await self.channels()
        if not forum: return 'Forum introuvable.'
        week=self.week_start(today)
        with connect() as db:
            if db.execute('SELECT 1 FROM regard_weekly_polls WHERE week_start=?',(week,)).fetchone(): return 'Vote déjà publié.'
            songs=db.execute('SELECT day,title,artist,url FROM regard_music WHERE day>=? AND day<=? ORDER BY day',(week,today.isoformat())).fetchall()
        if not songs: return 'Aucune musique disponible pour le vote.'
        lines=['🎵 **LA VOIX DE LA SEMAINE**','Vote ouvert jusqu’au dimanche prochain à 19h (heure de Paris). Un seul vote par personne, modifiable avant la clôture.','']
        for i,song in enumerate(songs,1):
            lines.append(f"**{i}. {discord.utils.escape_markdown(song['title'])} — {discord.utils.escape_markdown(song['artist'])}**\n{song['url']}")
        lines.append('\n🗳️ Vote avec `/regard_voter` et le numéro de ton titre préféré. Les votes ne donnent pas d’XP.')
        async with self.lock:
            with connect() as db:
                if db.execute('SELECT 1 FROM regard_weekly_polls WHERE week_start=?',(week,)).fetchone(): return 'Vote déjà publié.'
            result=await forum.create_thread(name='🎵 La Voix de la Semaine — '+today.strftime('%d/%m/%Y'),content='\n\n'.join(lines)[:1950],auto_archive_duration=10080,reason='Vote musical hebdomadaire HORIZONS',allowed_mentions=discord.AllowedMentions.none())
            with connect() as db:
                db.execute('INSERT INTO regard_weekly_polls(week_start,thread_id,created_at) VALUES(?,?,?)',(week,result.thread.id,datetime.now(TZ).isoformat()))
                for pos,song in enumerate(songs,1):
                    db.execute('INSERT OR IGNORE INTO regard_weekly_songs(week_start,position,day,title,artist,url) VALUES(?,?,?,?,?,?)',
                        (week,pos,song['day'],song['title'],song['artist'],song['url']))
        return f'Vote ouvert : {result.thread.mention}'

    @regard.command(name="voter",description='Voter pour la Voix de la Semaine (un vote modifiable).')
    @app_commands.describe(numero='Numéro de la chanson dans le sujet hebdomadaire')
    async def voter(self,interaction:discord.Interaction,numero:app_commands.Range[int,1,7]):
        if not ENABLED or not WEEKLY_VOTE_ENABLED or not interaction.guild or interaction.guild.id!=GUILD_ID:
            await interaction.response.send_message('Le vote musical est indisponible.',ephemeral=True);return
        today=datetime.now(TZ).date()
        with connect() as db:
            polls=db.execute('SELECT week_start FROM regard_weekly_polls WHERE closed_at IS NULL ORDER BY week_start DESC').fetchall()
        chosen=None
        for row in polls:
            start=datetime.fromisoformat(row['week_start']).date()
            if start<=today<start+timedelta(days=14):
                chosen=row['week_start'];break
        if not chosen:
            await interaction.response.send_message('Aucun vote ouvert actuellement.',ephemeral=True);return
        self.ensure_weekly_song_snapshot(chosen)
        with connect() as db:
            songs=db.execute('SELECT title FROM regard_weekly_songs WHERE week_start=? ORDER BY position',(chosen,)).fetchall()
            if not songs or numero>len(songs):
                await interaction.response.send_message(f'Choisis un numéro entre 1 et {len(songs)}.' if songs else 'Aucune chanson proposée.',ephemeral=True);return
            db.execute('INSERT INTO regard_weekly_votes(week_start,user_id,choice,voted_at) VALUES(?,?,?,?) ON CONFLICT(week_start,user_id) DO UPDATE SET choice=excluded.choice,voted_at=excluded.voted_at',
                (chosen,interaction.user.id,numero,datetime.now(TZ).isoformat()))
        await interaction.response.send_message(f'💙 Vote enregistré pour **{songs[numero-1][0]}** ! Tu peux changer ton choix avant la clôture.',ephemeral=True)

    @regard.command(name="vote_test",description='Publier le vote musical de la semaine pour vérification (staff).')
    async def vote_test(self,interaction:discord.Interaction):
        if not staff(interaction.user):
            await interaction.response.send_message('Commande réservée au staff.',ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        try: result=await self.publish_weekly_poll(datetime.now(TZ).date())
        except (discord.HTTPException,RuntimeError) as exc: result=f'Échec : {exc}'
        await interaction.followup.send(result,ephemeral=True)

    async def publish_weekly_recap(self, today):
        """Dimanche 18h30 : sommaire rétrospectif, sans reprendre les rumeurs."""
        forum,_=await self.channels()
        if not forum:return 'Forum absent.'
        week=self.week_start(today)
        with connect() as db:
            if db.execute('SELECT 1 FROM regard_weekly_digests WHERE week_start=?',(week,)).fetchone():return 'Bilan déjà publié.'
            posts=db.execute('SELECT day,thread_id FROM regard_posts WHERE day>=? AND day<=? ORDER BY day',(week,today.isoformat())).fetchall()
            articles=db.execute("SELECT title,url,category FROM regard_items WHERE day>=? AND day<=? AND status='approved' AND category!='🎵 Musique' ORDER BY day",(week,today.isoformat())).fetchall()
        if not posts:return 'Aucune édition cette semaine.'
        categories={}
        for a in articles:categories[a['category']]=categories.get(a['category'],0)+1
        lines=['🌌 **LES 7 JOURS SOUS LE MÊME CIEL**',
            f'Semaine du {week} · {len(posts)} édition(s) · {len(articles)} article(s) sourcé(s).',
            '📰 **Les éditions de la semaine :**']
        lines += [f'• {p["day"]} : https://discord.com/channels/{GUILD_ID}/{p["thread_id"]}' for p in posts]
        if categories:lines.append('**Thèmes suivis :** '+', '.join(f'{k} ({v})' for k,v in sorted(categories.items())))
        positive=next((x for x in articles if x['category']=='Solidarité'),None)
        if positive:lines.append('☀️ **La Lueur de la semaine :** '+shorten(positive['title'],150)+' — '+positive['url'])
        lines.append('🎵 Retrouve également **La Voix de la Semaine** pour voter parmi les découvertes musicales.')
        lines.append('💙 Merci de discuter avec respect : les accusations et les faits judiciaires ne se confondent pas.')
        async with self.lock:
            with connect() as db:
                if db.execute('SELECT 1 FROM regard_weekly_digests WHERE week_start=?',(week,)).fetchone():return 'Bilan déjà publié.'
            result=await forum.create_thread(name='🌌 Les 7 jours sous le même ciel — '+today.strftime('%d/%m/%Y'),
                content='\n\n'.join(lines)[:1950],auto_archive_duration=10080,reason='Bilan hebdomadaire HORIZONS',
                allowed_mentions=discord.AllowedMentions.none())
            with connect() as db:db.execute('INSERT OR IGNORE INTO regard_weekly_digests(week_start,thread_id,created_at) VALUES(?,?,?)',
                (week,result.thread.id,datetime.now(TZ).isoformat()))
        return f'Bilan publié : {result.thread.mention}'

    async def archive_old(self):
        forum,archive=await self.channels()
        if not forum: return
        cutoff=(datetime.now(TZ).date()-timedelta(days=30)).isoformat()
        with connect() as db:
            rows=db.execute('SELECT day,thread_id FROM regard_posts WHERE day<? AND archived_at IS NULL',(cutoff,)).fetchall()
        for row in rows:
            try:
                thread=forum.get_thread(row['thread_id']) or await self.bot.fetch_channel(row['thread_id'])
                if isinstance(thread, discord.Thread): await thread.edit(archived=True,locked=True,reason='Conservation des 30 derniers jours actifs')
                if archive: await archive.send(f"🗃️ Sujet du {row['day']} archivé : <#{row['thread_id']}>")
                with connect() as db: db.execute('UPDATE regard_posts SET archived_at=? WHERE day=?',(datetime.now(TZ).isoformat(),row['day']))
            except discord.HTTPException: logger.exception('Archivage Regard du Jour %s',row['day'])
        # Les bilans du dimanche rejoignent eux aussi l'historique technique.
        with connect() as db:
            digests=db.execute('SELECT week_start,thread_id FROM regard_weekly_digests WHERE week_start<?', (cutoff,)).fetchall()
            already={r['key'] for r in db.execute("SELECT key FROM regard_state WHERE key LIKE 'digest_archive:%'").fetchall()}
        for row in digests:
            key='digest_archive:'+row['week_start']
            if key in already:continue
            try:
                thread=forum.get_thread(row['thread_id']) or await self.bot.fetch_channel(row['thread_id'])
                if isinstance(thread,discord.Thread):await thread.edit(archived=True,locked=True,reason='Archivage du bilan hebdomadaire')
                if archive:await archive.send(f'🗃️ Bilan de la semaine du {row["week_start"]} : <#{row["thread_id"]}>')
                with connect() as db:db.execute('INSERT OR IGNORE INTO regard_state(key,value) VALUES(?,?)',(key,datetime.now(TZ).isoformat()))
            except discord.HTTPException:logger.exception('Archivage du bilan %s',row['week_start'])

    @tasks.loop(minutes=1)
    async def scheduler(self):
        # Ne jamais arrêter définitivement le rendez-vous quotidien sur une erreur isolée.
        try:await self._scheduler_tick()
        except Exception:logger.exception('Erreur inattendue du planificateur Regard du Jour')

    async def _scheduler_tick(self):
        if not ENABLED:return
        now=datetime.now(TZ);day=now.date().isoformat()
        with connect() as db:
            state=db.execute('SELECT value FROM regard_state WHERE key=?',('collect:'+day,)).fetchone()
        if now.hour>=16 and not state:
            count=await self.collect(day)
            with connect() as db:db.execute('INSERT OR IGNORE INTO regard_state(key,value) VALUES(?,?)',('collect:'+day,str(count)))
            if AUTO_MODE:
                chosen=self.auto_select(day)
                await self.notify_staff(f'📰 Regard du Jour : {count} liens vérifiés, {chosen} sélectionnés automatiquement. Vérification staff facultative via `/regard_selection`.')
            else:await self.notify_staff(f'📰 Regard du Jour : {count} candidats à valider avec `/regard_selection` et `/regard_valider`.')
        if now.hour>=PUBLISH_HOUR:
            with connect() as db:posted=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(day,)).fetchone()
            # Une collecte complète supplémentaire au maximum à 18h, en cas de panne RSS à 16h.
            with connect() as db: retried=db.execute('SELECT value FROM regard_state WHERE key=?',('retry:'+day,)).fetchone()
            if AUTO_MODE and not posted and (not retried or retried['value'] != now.strftime('%Y-%m-%dT%H')):
                with connect() as db:db.execute('INSERT OR REPLACE INTO regard_state(key,value) VALUES(?,?)',('retry:'+day,now.strftime('%Y-%m-%dT%H')))
                try:
                    await self.collect(day)
                    self.auto_select(day)
                except (aiohttp.ClientError,asyncio.TimeoutError) as exc:logger.warning('Nouvelle collecte impossible : %s',exc)
            try:
                with connect() as db: parts=db.execute('SELECT COUNT(*) FROM regard_thread_parts WHERE day=?',(day,)).fetchone()[0]
                if not posted or parts<3:
                    result=await self.publish(day)
                    if result.startswith('Publié'):await self.notify_staff(result)
                elif posted:
                    # Reprend des parties manquantes même si le bot a redémarré au milieu.
                    with connect() as db:
                        expected=db.execute("SELECT COUNT(*) FROM regard_items WHERE day=? AND status='approved' AND category!='🎵 Musique'",(day,)).fetchone()[0]+4
                        indexed=db.execute('SELECT 1 FROM regard_state WHERE key=?',('index:'+day,)).fetchone()
                    if parts<expected or not indexed:await self.publish(day)
            except (discord.HTTPException,RuntimeError,aiohttp.ClientError,asyncio.TimeoutError):logger.exception('Publication Regard du Jour')
            try:await self.archive_old()
            except discord.HTTPException:logger.exception('Archivage Regard du Jour')
        if now.weekday()==6:
            if WEEKLY_RECAP_ENABLED and (now.hour,now.minute)>=(WEEKLY_RECAP_HOUR,WEEKLY_RECAP_MINUTE):
                try:await self.publish_weekly_recap(now.date())
                except (discord.HTTPException,RuntimeError):logger.exception('Bilan hebdomadaire Regard du Jour')
            if WEEKLY_VOTE_ENABLED and now.hour>=WEEKLY_VOTE_HOUR:
                try:
                    await self.close_weekly_poll(self.week_start(now.date()-timedelta(days=7)))
                    await self.publish_weekly_poll(now.date())
                except (discord.HTTPException,RuntimeError):logger.exception('Vote musical hebdomadaire HORIZONS')

    @scheduler.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()

    @regard.command(name="installer",description='Créer le forum public et le journal technique (administration).')
    @app_commands.checks.has_permissions(administrator=True)
    async def installer(self,interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            forum,archive=await self.channels(create=True)
            await interaction.followup.send(f'Forum : {forum.mention}\nJournal technique : {archive.mention}\nRenseigne leurs IDs dans `.env` pour fiabiliser les redémarrages. Active `REGARD_ENABLED=true` lorsque tu es prêt.',ephemeral=True)
        except (discord.HTTPException,RuntimeError) as exc: await interaction.followup.send(f'Installation impossible : {exc}',ephemeral=True)

    # Migré vers /dashboard → Regardboard.

    # @regard.command(name="collecter")
    async def collecter(self,interaction:discord.Interaction):
        if not staff(interaction.user): return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        count=await self.collect(datetime.now(TZ).date().isoformat())
        await interaction.followup.send(f'{count} nouveau(x) lien(s) ajouté(s) à la file de validation.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.
    # @regard.command(name="selection",description='Voir les articles en attente de validation (staff).')
    async def selection(self,interaction:discord.Interaction):
        if not staff(interaction.user): return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        with connect() as db: rows=db.execute('SELECT id,title,category,status FROM regard_items WHERE day=? ORDER BY id DESC LIMIT 18',(datetime.now(TZ).date().isoformat(),)).fetchall()
        lines=[f"`#{r['id']}` [{r['status']}] {r['category']} — {shorten(r['title'],105)}" for r in rows]
        await interaction.response.send_message('\n'.join(lines)[:1950] if lines else 'Aucun article candidat. Utilise `/regard_collecter`.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.
    # @regard.command(name="valider")
    @app_commands.describe(article_id='Numéro affiché dans /regard_selection',decision='Approuver ou refuser')
    @app_commands.choices(decision=[app_commands.Choice(name='Approuver',value='approved'),app_commands.Choice(name='Refuser',value='rejected')])
    async def valider(self,interaction:discord.Interaction,article_id:int,decision:app_commands.Choice[str]):
        if not staff(interaction.user): return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        with connect() as db:
            row=db.execute('SELECT title FROM regard_items WHERE id=?',(article_id,)).fetchone()
            if row: db.execute('UPDATE regard_items SET status=?,reviewed_by=? WHERE id=?',(decision.value,interaction.user.id,article_id))
        await interaction.response.send_message(f"Article #{article_id} : {decision.name}." if row else 'Article introuvable.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.

    # @regard.command(name="ajouter")
    async def ajouter(self,interaction:discord.Interaction,titre:str,lien:str,musique:bool=False):
        if not staff(interaction.user): return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        if not lien.startswith('https://') or len(titre)>200: return await interaction.response.send_message('Titre trop long ou lien HTTPS invalide.',ephemeral=True)
        with connect() as db:
            cur=db.execute('INSERT OR IGNORE INTO regard_items(day,title,url,category,status,created_at,reviewed_by) VALUES(?,?,?,?,?,?,?)',
                (datetime.now(TZ).date().isoformat(),titre,lien,'🎵 Musique' if musique else 'Proposition staff','approved',datetime.now(TZ).isoformat(),interaction.user.id))
        await interaction.response.send_message('Ajout validé.' if cur.rowcount else 'Lien déjà présent.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.
    # @regard.command(name="diagnostic",description='Afficher le diagnostic de la collecte et la configuration (staff).')
    async def diagnostic(self, interaction:discord.Interaction):
        if not staff(interaction.user):
            return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        day=datetime.now(TZ).date().isoformat()
        with connect() as db:
            state=db.execute('SELECT value FROM regard_state WHERE key=?',('diagnostic:'+day,)).fetchone()
            counts=db.execute('SELECT status,COUNT(*) AS n FROM regard_items WHERE day=? GROUP BY status',(day,)).fetchall()
            post=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(day,)).fetchone()
        forum,_=await self.channels()
        lines=[f'📰 **Diagnostic Regard — {day}**',
               f'Actif : **{ENABLED}** · Auto : **{AUTO_MODE}** · Heure : **{PUBLISH_HOUR}h** (Paris)',
               f'Forum : **{"OK" if forum else "ABSENT"}** · Sujet créé : **{bool(post)}**',
               'Articles : '+(', '.join(f'{r["status"]}={r["n"]}' for r in counts) or 'aucun'),
               'Collecte : '+(state['value'][:1100] if state else 'aucun diagnostic enregistré'),
               'Configuration : '+('fichier .env présent' if (DATA_DIR.parent / '.env').is_file() else 'fichier .env absent (variables hébergeur utilisées)')+
               ' · REGARD_ENABLED lu='+repr(os.getenv('REGARD_ENABLED', '<absent>'))]
        await interaction.response.send_message('\n'.join(lines)[:1950],ephemeral=True)

    @regard.command(name="publier",description='Publier manuellement les contenus validés du jour (staff).')
    async def publier(self,interaction:discord.Interaction):
        if not staff(interaction.user): return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            day=datetime.now(TZ).date().isoformat()
            with connect() as db:
                ready=db.execute("SELECT COUNT(*) FROM regard_items WHERE day=? AND status='approved' AND category!='🎵 Musique'",(day,)).fetchone()[0]
            if not ready and AUTO_MODE:
                await self.collect(day)
                self.auto_select(day)
            msg=await self.publish(day)
        except (RuntimeError,discord.HTTPException) as exc: msg=f'Échec : {exc}'
        await interaction.followup.send(msg,ephemeral=True)

    @regard.command(name="regenerer",description='Reconstruire l’édition du jour après confirmation (staff).')
    @app_commands.describe(confirmer='Mettre Oui pour remplacer le sujet existant après vérification')
    async def regenerer(self, interaction:discord.Interaction, confirmer:bool=False):
        if not staff(interaction.user):
            return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        day=datetime.now(TZ).date().isoformat()
        if not confirmer:
            with connect() as db:
                n=db.execute("SELECT COUNT(*) FROM regard_items WHERE day=? AND category!='🎵 Musique' AND status IN ('approved','pending')",(day,)).fetchone()[0]
                old=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(day,)).fetchone()
            return await interaction.response.send_message(
                f'📰 **Prévisualisation de régénération — {day}**\n'
                f'{n} article(s) disponibles pour une nouvelle sélection.\n'
                f'Sujet existant : {"oui" if old else "non"}.\n'
                'Cette opération peut remplacer le sujet du jour et ses réponses. '
                'Les autres journées, XP et archives SQLite sont conservés.\n'
                '**Pour confirmer :** `/regard_regenerer confirmer:Oui`.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        async with self.regeneration_lock:
            # Prépare la nouvelle sélection sans supprimer les données existantes.
            with connect() as db:
                backup_status=[(r['id'],r['status'],r['reviewed_by']) for r in db.execute(
                    "SELECT id,status,reviewed_by FROM regard_items WHERE day=? AND category!='🎵 Musique'",(day,))]
                previous=db.execute('SELECT * FROM regard_posts WHERE day=?',(day,)).fetchone()
                previous_parts=[(r['part_key'],r['message_id']) for r in db.execute('SELECT part_key,message_id FROM regard_thread_parts WHERE day=?',(day,))]
                previous_index=db.execute('SELECT value FROM regard_state WHERE key=?',('index:'+day,)).fetchone()
            new_thread_id=None
            try:
                # Les anciennes validations automatiques sont recalculées; les choix
                # explicitement effectués par le staff restent prioritaires.
                with connect() as db:
                    db.execute("UPDATE regard_items SET status='pending' WHERE day=? AND status='approved' AND reviewed_by IS NULL AND category!='🎵 Musique'",(day,))
                await self.collect(day)
                self.auto_select(day)
                with connect() as db:
                    selected=db.execute("SELECT id,title FROM regard_items WHERE day=? AND status='approved' AND category!='🎵 Musique' ORDER BY id LIMIT ?",(day,ARTICLE_MAX)).fetchall()
                if not selected:
                    raise RuntimeError('Aucun article fiable sélectionné : ancienne publication conservée.')
                # Empêche une régénération lorsque les anciens choix du staff
                # remplissent déjà les cinq places, sans masquer cette limite.
                with connect() as db:
                    db.execute('DELETE FROM regard_thread_parts WHERE day=?',(day,))
                    db.execute('DELETE FROM regard_state WHERE key=?',('index:'+day,))
                # publish utilise son propre verrou; celui-ci est libéré le temps
                # de l’appel, tandis que le scheduler vérifie l’état SQLite.
            except Exception as exc:
                with connect() as db:
                    for item_id,status,reviewed_by in backup_status:
                        db.execute('UPDATE regard_items SET status=?,reviewed_by=? WHERE id=?',(status,reviewed_by,item_id))
                return await interaction.followup.send(f'Régénération annulée : {exc}',ephemeral=True)
        # La publication construit un nouveau fil. En cas d’échec, restaurer
        # les références précédentes pour pouvoir retenter sans perte.
        try:
            result=await self.publish(day,rebuild=True)
            with connect() as db:
                current=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(day,)).fetchone()
                new_thread_id=current['thread_id'] if current else None
            if previous and previous['thread_id']!=new_thread_id:
                try:
                    old_thread=self.bot.get_channel(previous['thread_id']) or await self.bot.fetch_channel(previous['thread_id'])
                    if isinstance(old_thread,discord.Thread):
                        await old_thread.delete(reason='Regard du Jour régénéré et remplacé par le staff')
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    logger.exception('Ancien sujet Regard non supprimé ; nettoyage manuel possible')
                    result+='\n⚠️ Ancien sujet non supprimé : vérifie le forum pour éviter un doublon.'
            await interaction.followup.send('✅ '+result+'\nNouvelle sélection : '+str(len(selected))+' article(s).',ephemeral=True)
        except Exception as exc:
            logger.exception('Échec de régénération Regard %s',day)
            with connect() as db:
                for item_id,status,reviewed_by in backup_status:
                    db.execute('UPDATE regard_items SET status=?,reviewed_by=? WHERE id=?',(status,reviewed_by,item_id))
                db.execute('DELETE FROM regard_thread_parts WHERE day=?',(day,))
                db.executemany('INSERT INTO regard_thread_parts(day,part_key,message_id) VALUES(?,?,?)',
                               [(day,k,v) for k,v in previous_parts])
                db.execute('DELETE FROM regard_posts WHERE day=?',(day,))
                if previous:
                    db.execute('INSERT INTO regard_posts(day,thread_id,published_at,archived_at) VALUES(?,?,?,?)',
                               (day,previous['thread_id'],previous['published_at'],previous['archived_at']))
                db.execute('DELETE FROM regard_state WHERE key=?',('index:'+day,))
                if previous_index:
                    db.execute('INSERT INTO regard_state(key,value) VALUES(?,?)',('index:'+day,previous_index['value']))
            if new_thread_id and (not previous or new_thread_id != previous['thread_id']):
                try:
                    orphan=self.bot.get_channel(new_thread_id) or await self.bot.fetch_channel(new_thread_id)
                    if isinstance(orphan,discord.Thread):
                        await orphan.delete(reason='Nettoyage d’une régénération interrompue')
                except discord.HTTPException:
                    logger.warning('Nettoyage manuel nécessaire pour le sujet incomplet %s',new_thread_id)
            await interaction.followup.send(f'❌ Régénération interrompue : {type(exc).__name__}. Ancienne édition conservée.',ephemeral=True)

    @regard.command(name="retirer",description='Retirer un article public avec trace de modération (staff).')
    @app_commands.describe(article_id='Identifiant visible dans /regard_selection',motif='Raison courte du retrait')
    async def retirer(self,interaction:discord.Interaction,article_id:int,motif:str='Information à revérifier'):
        if not staff(interaction.user):return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        with connect() as db:
            item=db.execute('SELECT * FROM regard_items WHERE id=?',(article_id,)).fetchone()
            if not item:return await interaction.followup.send('Article introuvable.',ephemeral=True)
            post=db.execute('SELECT thread_id FROM regard_posts WHERE day=?',(item['day'],)).fetchone()
            part=db.execute('SELECT message_id FROM regard_thread_parts WHERE day=? AND part_key=?',
                (item['day'],f'article:{article_id}')).fetchone()
        if part and post:
            try:
                thread=self.bot.get_channel(post['thread_id']) or await self.bot.fetch_channel(post['thread_id'])
                if isinstance(thread,discord.Thread):
                    message=await thread.fetch_message(part['message_id'])
                    await message.edit(content=f'⚠️ **Article retiré par l’équipe HORIZONS.**\nMotif : {shorten(motif,250)}',
                        allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException as exc:
                return await interaction.followup.send(f'Retrait Discord impossible ; article conservé pour ne pas masquer l’échec : {exc}',ephemeral=True)
        with connect() as db:db.execute("UPDATE regard_items SET status='rejected',reviewed_by=? WHERE id=?",(interaction.user.id,article_id))
        await self.notify_staff(f'🛡️ Article #{article_id} retiré par {interaction.user.id} : {shorten(motif,180)}')
        await interaction.followup.send('✅ Article retiré et consigné.',ephemeral=True)

    # Action accessible depuis /centre → Regard du Jour.
    # @regard.command(name="proposer",description='Proposer un article ou une chanson au staff HORIZONS.')
    @app_commands.describe(titre='Titre à vérifier',lien='Lien HTTPS vers la source',musique='S’agit-il d’une musique ?')
    async def proposer(self,interaction:discord.Interaction,titre:str,lien:str,musique:bool=False):
        if not interaction.guild or interaction.guild.id!=GUILD_ID or not isinstance(interaction.user,discord.Member):
            return await interaction.response.send_message('Commande réservée aux membres HORIZONS.',ephemeral=True)
        if MEMBER_ROLE_ID and not any(r.id==MEMBER_ROLE_ID for r in interaction.user.roles) and not staff(interaction.user):
            return await interaction.response.send_message('Valide d’abord la charte pour proposer un contenu.',ephemeral=True)
        parsed=urlsplit(lien)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or len(lien)>900 or len(titre)>170 or len(titre.strip())<12:
            return await interaction.response.send_message('Utilise un titre de 12 à 170 caractères et un lien HTTPS public valide.',ephemeral=True)
        if parsed.hostname in {'localhost','127.0.0.1','0.0.0.0'} or parsed.hostname.endswith('.local'):
            return await interaction.response.send_message('Lien non accepté.',ephemeral=True)
        with connect() as db:
            # Limiter le volume des propositions d'une même personne.
            sent=db.execute("SELECT COUNT(*) FROM regard_proposals WHERE guild_id=? AND user_id=? AND created_at>=?",(interaction.guild.id,interaction.user.id,(datetime.now(TZ)-timedelta(days=1)).isoformat())).fetchone()[0]
            if sent>=3:return await interaction.response.send_message('Tu peux proposer jusqu’à trois liens par jour. 💙',ephemeral=True)
            cur=db.execute('INSERT OR IGNORE INTO regard_proposals(guild_id,user_id,url,kind,title,created_at) VALUES(?,?,?,?,?,?)',
                (interaction.guild.id,interaction.user.id,lien,'musique' if musique else 'article',titre.strip(),datetime.now(TZ).isoformat()))
        if cur.rowcount:
            await self.notify_staff(f'🧭 **Nouvelle proposition #{cur.lastrowid}** ({"musique" if musique else "article"}) : {discord.utils.escape_markdown(titre[:160])}\n{lien}\nTraite-la dans `/dashboard` → Regardboard après avoir consulté la source.')
        await interaction.response.send_message('💙 Proposition enregistrée pour vérification par le staff.' if cur.rowcount else 'Ce lien a déjà été proposé.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.
    # @regard.command(name="propositions")
    async def propositions(self,interaction:discord.Interaction):
        if not staff(interaction.user):return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        with connect() as db:rows=db.execute("SELECT id,kind,title FROM regard_proposals WHERE status='pending' ORDER BY id LIMIT 15").fetchall()
        await interaction.response.send_message('\n'.join(f'`#{r["id"]}` {r["kind"]} — {shorten(r["title"],95)}' for r in rows)[:1950] if rows else 'Aucune proposition en attente.',ephemeral=True)

    # Migré vers /dashboard → Regardboard.
    # @regard.command(name="proposition_valider")
    @app_commands.choices(decision=[app_commands.Choice(name='Approuver',value='approved'),app_commands.Choice(name='Refuser',value='rejected')])
    async def proposition_valider(self,interaction:discord.Interaction,numero:int,decision:app_commands.Choice[str]):
        if not staff(interaction.user):return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        with connect() as db:
            proposal=db.execute("SELECT * FROM regard_proposals WHERE id=? AND status='pending'",(numero,)).fetchone()
            if not proposal:return await interaction.response.send_message('Proposition introuvable ou déjà traitée.',ephemeral=True)
            db.execute('UPDATE regard_proposals SET status=?,reviewed_by=? WHERE id=?',(decision.value,interaction.user.id,numero))
            if decision.value=='approved':
                day=datetime.now(TZ).date().isoformat()
                db.execute("""INSERT OR IGNORE INTO regard_items(day,title,url,category,status,created_at,source,source_url)
                  VALUES(?,?,?,?,?,?,?,?)""",(day,proposal['title'],proposal['url'],
                    '🎵 Musique' if proposal['kind']=='musique' else 'Proposition de la communauté',
                    'approved',datetime.now(TZ).isoformat(),'Proposition vérifiée par le staff',proposal['url']))
        await interaction.response.send_message(f'Proposition #{numero} : {decision.name}. Les articles approuvés seront pris en compte dans la prochaine sélection ; les chansons proposées restent dans le registre staff.',ephemeral=True)

    @regard.command(name="bilan_test",description='Tester la publication du bilan hebdomadaire (staff).')
    async def bilan_test(self,interaction:discord.Interaction):
        if not staff(interaction.user):return await interaction.response.send_message('Réservé au staff.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:result=await self.publish_weekly_recap(datetime.now(TZ).date())
        except (discord.HTTPException,RuntimeError) as exc:result=f'Erreur : {exc}'
        await interaction.followup.send(result,ephemeral=True)

    # Action accessible depuis /centre → Regard du Jour.
    # @regard.command(name="points",description='Voir tes XP Célestes gagnés dans Le Regard du Jour.')
    async def points(self,interaction:discord.Interaction):
        if not interaction.guild_id:return await interaction.response.send_message('À utiliser sur le serveur.',ephemeral=True)
        with connect() as db:
            earned=db.execute('SELECT COALESCE(SUM(points),0) FROM regard_xp WHERE guild_id=? AND user_id=?',(interaction.guild_id,interaction.user.id)).fetchone()[0]
            today=db.execute('SELECT points FROM regard_xp WHERE guild_id=? AND user_id=? AND day=?',(interaction.guild_id,interaction.user.id,datetime.now(TZ).date().isoformat())).fetchone()
        total=total_xp(interaction.guild_id,interaction.user.id)
        await interaction.response.send_message(f'🌟 **{earned} XP Célestes** gagnés dans Le Regard du Jour, dont {int(today[0]) if today else 0}/{XP_DAILY_LIMIT} aujourd’hui. Total HORIZONS : **{total} XP Célestes**.',ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        if not ENABLED or not message.guild or message.author.bot or message.guild.id!=GUILD_ID:return
        content=message.content.strip()
        if len(content)<45 or content.startswith(('/','!')):return
        if message.id in getattr(self.bot,'automod_blocked_message_ids',set()):return
        if not isinstance(message.channel,discord.Thread):return
        forum,_=await self.channels()
        if not forum or message.channel.parent_id!=forum.id:return
        # Uniquement les sujets quotidiens : pas de prime aux votes et aux discussions techniques.
        fp=hashlib.sha256(' '.join(normalize(content).split()).encode('utf-8')).hexdigest()
        now=datetime.now(TZ);today=now.date().isoformat()
        with connect() as db:
            known=db.execute('SELECT day FROM regard_posts WHERE thread_id=?',(message.channel.id,)).fetchone()
            if not known or (today-datetime.fromisoformat(known['day']).date()).days>2:return
            if db.execute('SELECT 1 FROM regard_xp_audit WHERE message_id=?',(message.id,)).fetchone():return
            current=db.execute('SELECT points FROM regard_xp WHERE guild_id=? AND user_id=? AND day=?',(message.guild.id,message.author.id,today)).fetchone()
            points=int(current[0]) if current else 0
            if points>=XP_DAILY_LIMIT:return
            last=db.execute('SELECT fingerprint,awarded_at FROM regard_xp_audit WHERE guild_id=? AND user_id=? ORDER BY awarded_at DESC LIMIT 1',(message.guild.id,message.author.id)).fetchone()
            if last and (last['fingerprint']==fp or (now-datetime.fromisoformat(last['awarded_at'])).total_seconds()<XP_COOLDOWN_SECONDS):return
            if db.execute('SELECT 1 FROM regard_xp_audit WHERE guild_id=? AND user_id=? AND day=? AND fingerprint=?',(message.guild.id,message.author.id,today,fp)).fetchone():return
            wanted=min(5 if points==0 else 3,XP_DAILY_LIMIT-points)
            # Même portefeuille que l'Arcade. La récompense se dédoublonne avec la clé du message.
            try:granted=award_xp(message.guild.id,message.author.id,f'regard:{today}:{message.id}',wanted)
            except (sqlite3.DatabaseError,ValueError):logger.exception('Attribution XP HORIZONS');return
            db.execute('INSERT OR IGNORE INTO regard_xp_audit(message_id,guild_id,user_id,day,fingerprint,awarded_at,points) VALUES(?,?,?,?,?,?,?)',
                (message.id,message.guild.id,message.author.id,today,fp,now.isoformat(),granted))
            if granted:
                db.execute('INSERT INTO regard_xp(guild_id,user_id,day,points) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id,day) DO UPDATE SET points=points+excluded.points',
                    (message.guild.id,message.author.id,today,granted))

async def setup(bot): await bot.add_cog(RegardDuJour(bot))
