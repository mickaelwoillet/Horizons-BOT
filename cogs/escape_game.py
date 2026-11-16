"""HORIZONS Escape Game : portail et installation idempotente des 3 aventures.

Portail, installation idempotente et gestion des équipes.
"""
from __future__ import annotations
import asyncio
import json
import sqlite3
import os
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR
from .embed_theme import horizons_embed
from escape_engine import Engine, load_adventure, AdventureError
from escape_ui import show_room

DB = DATA_DIR / 'escape_game.sqlite3'
STATE = DATA_DIR / 'escape_installation.json'

def save_installation(state):
 """Persist progress atomically, including partial installations."""
 STATE.parent.mkdir(parents=True, exist_ok=True)
 tmp = STATE.with_name(STATE.name + '.tmp')
 try:
  tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
  os.replace(tmp, STATE)
 finally:
  if tmp.exists():
   tmp.unlink()

CATEGORY = '🔐 ESCAPE GAME'
CHANNELS = [
 ('🚪・escape-game', 'Portail des Escape Games HORIZONS'),
 ('🌌・fractures-du-cosmos', 'Les Fractures du Cosmos — aventure cosmique'),
 ('🏚️・manoir-des-murmures', 'Le Manoir des Murmures — bientôt disponible'),
 ('🌊・cite-engloutie', 'La Cité Engloutie — bientôt disponible'),
 ('🧩・entraide-escape-game', 'Trouver une équipe et échanger sans spoilers'),
]

def db():
 DB.parent.mkdir(parents=True,exist_ok=True)
 conn=sqlite3.connect(DB)
 conn.execute('PRAGMA foreign_keys=ON')
 conn.executescript("""CREATE TABLE IF NOT EXISTS progress (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, adventure TEXT NOT NULL, room INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(guild_id,user_id,adventure));
 CREATE TABLE IF NOT EXISTS teams (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, adventure TEXT NOT NULL, leader_id INTEGER NOT NULL, room INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS team_members (team_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(team_id,user_id), FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE);
 CREATE TABLE IF NOT EXISTS inventory (guild_id INTEGER NOT NULL, mode TEXT NOT NULL, owner_id INTEGER NOT NULL, adventure TEXT NOT NULL, item TEXT NOT NULL, PRIMARY KEY(guild_id,mode,owner_id,adventure,item));
 CREATE TABLE IF NOT EXISTS team_invitations (team_id INTEGER NOT NULL, user_id INTEGER NOT NULL, invited_by INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(team_id,user_id), FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE);""")
 return conn

def emb(title, description):
 return discord.Embed(title=title, description=description, color=discord.Color.from_rgb(198,153,63))

class Portal(discord.ui.View):
 def __init__(self):
  super().__init__(timeout=None)
 @discord.ui.button(label='Jouer en solo',style=discord.ButtonStyle.primary,emoji='🌌',custom_id='escape:solo')
 async def solo(self, interaction:discord.Interaction, button:discord.ui.Button):
  with db() as con:
   con.execute('INSERT OR IGNORE INTO progress(guild_id,user_id,adventure) VALUES(?,?,?)',(interaction.guild_id,interaction.user.id,'fractures'))
  await interaction.response.send_message('🌌 **Les Fractures du Cosmos** : ton profil Solo est prêt. Lance `/escape jouer` en mode Solo pour ouvrir ta salle. Ta progression est conservée.',ephemeral=True)
 @discord.ui.button(label='Créer une équipe',style=discord.ButtonStyle.secondary,emoji='👥',custom_id='escape:team')
 async def team(self, interaction:discord.Interaction, button:discord.ui.Button):
  with db() as con:
   current=con.execute('SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,'fractures',interaction.user.id)).fetchone()
   if current:
    return await interaction.response.send_message(f'👥 Tu fais déjà partie de l’équipe **#{current[0]}**.',ephemeral=True)
   cur=con.execute('INSERT INTO teams(guild_id,adventure,leader_id) VALUES(?,?,?)',(interaction.guild_id,'fractures',interaction.user.id))
   team_id=cur.lastrowid
   con.execute('INSERT INTO team_members(team_id,user_id) VALUES(?,?)',(team_id,interaction.user.id))
  await interaction.response.send_message(f'👥 Équipe **#{team_id}** créée ! Pour inviter jusqu’à cinq personnes, utilise `/escape inviter` avec le numéro de ton équipe. Lance `/escape jouer` en mode Collectif pour commencer.',ephemeral=True)
 @discord.ui.button(label='Ma progression',style=discord.ButtonStyle.secondary,emoji='💾',custom_id='escape:progress')
 async def progress(self, interaction:discord.Interaction, button:discord.ui.Button):
  with db() as con:
   solo=con.execute('SELECT room FROM progress WHERE guild_id=? AND user_id=? AND adventure=?',(interaction.guild_id,interaction.user.id,'fractures')).fetchone()
   team=con.execute('SELECT t.id,t.room FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,'fractures',interaction.user.id)).fetchone()
  msg=f'**Solo :** {"profil créé" if solo else "pas encore commencé"}\\n**Équipe :** {"#"+str(team[0]) if team else "aucune"}\\nUtilise `/escape jouer` pour reprendre ta partie.'
  await interaction.response.send_message(msg.replace('\\n','\n'),ephemeral=True)
 @discord.ui.button(label='Les aventures',style=discord.ButtonStyle.secondary,emoji='🗝️',custom_id='escape:catalog')
 async def catalog(self,interaction:discord.Interaction,button:discord.ui.Button):
  await interaction.response.send_message(embed=emb('🗝️ Le catalogue des aventures','🌌 **Les Fractures du Cosmos** — jouable avec `/escape jouer`\n🏚️ **Le Manoir des Murmures** — à venir\n🌊 **La Cité Engloutie** — à venir'),ephemeral=True)

CONTENT_FILE = Path(__file__).resolve().parents[1] / 'escape_content' / 'fractures.json'

class EscapeGame(commands.GroupCog, group_name='escape', group_description='Portail et gestion des Escape Games HORIZONS'):
 def __init__(self,bot): self.bot=bot; self.lock=asyncio.Lock()
 async def cog_load(self):
  with db(): pass
  self.bot.add_view(Portal())
 @app_commands.command(name='jouer', description='Ouvrir ta salle actuelle dans Les Fractures du Cosmos.')
 @app_commands.describe(mode='Choisir Solo ou Collectif')
 @app_commands.choices(mode=[app_commands.Choice(name='Solo',value='solo'), app_commands.Choice(name='Collectif',value='team')])
 async def jouer(self, interaction:discord.Interaction, mode:app_commands.Choice[str]):
  if not interaction.guild:
   return await interaction.response.send_message('Commande disponible uniquement sur le serveur.', ephemeral=True)
  if not CONTENT_FILE.is_file():
   return await interaction.response.send_message('🔐 Cette aventure est encore en préparation.', ephemeral=True)
  try:
   content=load_adventure(CONTENT_FILE)
  except (ValueError,KeyError,OSError) as exc:
   return await interaction.response.send_message('⚠️ Le contenu de cette aventure est momentanément indisponible.', ephemeral=True)
  if mode.value=='solo':
   owner=interaction.user.id
  else:
   with db() as con:
    team=con.execute('SELECT t.id FROM teams t JOIN team_members m ON t.id=m.team_id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?', (interaction.guild_id,'fractures',interaction.user.id)).fetchone()
   if not team:
    return await interaction.response.send_message('Rejoins ou crée une équipe avant de jouer en collectif.', ephemeral=True)
   owner=team[0]
  engine=Engine(DB)
  engine.start(interaction.guild_id,'fractures',mode.value,owner,content['rooms'][0]['id'])
  await show_room(interaction,engine,content,(interaction.guild_id,'fractures',mode.value,owner))

 @app_commands.command(name='installer',description='Installer la catégorie Escape Game et ses cinq salons (administration).')
 @app_commands.default_permissions(administrator=True)
 async def installer(self,interaction:discord.Interaction):
  if not interaction.guild or not interaction.user.guild_permissions.administrator:
   return await interaction.response.send_message('Commande réservée aux administrateurs.',ephemeral=True)
  bot_member = interaction.guild.me
  if bot_member is None:
   return await interaction.response.send_message('Impossible de vérifier les permissions du bot.',ephemeral=True)
  perms = bot_member.guild_permissions
  if not (perms.manage_channels and perms.send_messages and perms.read_message_history and perms.view_channel):
   return await interaction.response.send_message('Permissions nécessaires : Gérer les salons, Voir les salons, Envoyer des messages et Lire l’historique.',ephemeral=True)
  await interaction.response.defer(ephemeral=True,thinking=True)
  async with self.lock:
   guild=interaction.guild
   state={}
   if STATE.exists():
    try: state=json.loads(STATE.read_text(encoding='utf-8'))
    except (ValueError,OSError): pass
   gs=state.setdefault(str(guild.id),{})
   category=guild.get_channel(gs.get('category_id',0))
   if not isinstance(category,discord.CategoryChannel):
    category=discord.utils.get(guild.categories,name=CATEGORY)
   try:
    if category is None: category=await guild.create_category(CATEGORY,reason='Installation Escape Game HORIZONS')
    gs['category_id']=category.id
    save_installation(state)
    channels=gs.setdefault('channels',{})
    created=[]
    for name,topic in CHANNELS:
     channel=guild.get_channel(channels.get(name,0))
     if not isinstance(channel,discord.TextChannel) or channel.category_id != category.id:
      channel=discord.utils.get(category.text_channels,name=name)
     if channel is None:
      channel=await guild.create_text_channel(name,category=category,topic=topic,reason='Installation Escape Game HORIZONS')
      created.append(name)
     channels[name]=channel.id
     save_installation(state)
    panels={
     CHANNELS[0][0]:(emb('🔐 ESCAPE GAME — HORIZONS','Bienvenue dans le portail des aventures !\n\n🌌 **Les Fractures du Cosmos** — jouable avec `/escape jouer`\n🏚️ **Le Manoir des Murmures** — à venir prochainement\n🌊 **La Cité Engloutie** — à venir prochainement\n\nDeux modes : **Solo** et **Collectif**. Utilise `/escape jouer` pour ouvrir ta salle.'),Portal()),
     CHANNELS[1][0]:(emb('🌌 Les Fractures du Cosmos','Les étoiles s’éteignent une à une. Un observatoire oublié s’éveille…\n\n**L’aventure t’attend.** Utilise `/escape jouer` pour entrer dans ta salle.\n\n**🔎 Cliquer sur l’image pour l’agrandir.**'),None),
     CHANNELS[2][0]:(emb('🏚️ Le Manoir des Murmures','Une demeure, des secrets et des voix qui ne devraient plus résonner.\n\n**À venir prochainement.**'),None),
     CHANNELS[3][0]:(emb('🌊 La Cité Engloutie','Sous les eaux sommeille une civilisation oubliée.\n\n**À venir prochainement.**'),None),
     CHANNELS[4][0]:(emb('🧩 Entraide Escape Game','Trouvez vos partenaires et partagez vos théories !\n\n**Pas de spoilers :** évitez les réponses, codes et captures révélant les solutions.'),None),
    }
    messages=gs.setdefault('messages',{})
    for name,(embed,view) in panels.items():
     channel=guild.get_channel(channels[name]);message=None
     mid=messages.get(name)
     if mid:
      try: message=await channel.fetch_message(mid)
      except (discord.NotFound, discord.Forbidden, discord.HTTPException): pass
     if message is None:
      try:
       async for old in channel.history(limit=50):
        if self.bot.user and old.author.id==self.bot.user.id and old.embeds and old.embeds[0].title==embed.title:
         message=old;break
      except (discord.Forbidden, discord.HTTPException):
       pass
     if message: await message.edit(embed=embed,view=view)
     else: message=await channel.send(embed=embed,view=view)
     messages[name]=message.id
     save_installation(state)
    save_installation(state)
    await interaction.followup.send(f'✅ Espace Escape Game installé : **{len(created)} nouveaux salons**, **{len(CHANNELS)} panneaux vérifiés**. Le portail des Fractures du Cosmos est configuré.',ephemeral=True)
   except discord.HTTPException as exc:
    save_installation(state)
    await interaction.followup.send(f'⚠️ Installation interrompue : {exc}. Relance `/escape installer` après correction ; les éléments existants seront réutilisés.',ephemeral=True)
 @app_commands.command(name='inviter',description='Inviter un membre dans son équipe Escape Game (maximum 6).')
 @app_commands.describe(equipe='Numéro de ton équipe',membre='Membre à inviter')
 async def inviter(self,interaction:discord.Interaction,equipe:int,membre:discord.Member):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  if membre.bot: return await interaction.response.send_message('Les bots ne peuvent pas rejoindre une équipe.',ephemeral=True)
  with db() as con:
   leader=con.execute('SELECT leader_id FROM teams WHERE id=? AND guild_id=?',(equipe,interaction.guild_id)).fetchone()
   if not leader or leader[0]!=interaction.user.id:
    return await interaction.response.send_message('Seul le capitaine peut inviter dans cette équipe.',ephemeral=True)
   count=con.execute('SELECT COUNT(*) FROM team_members WHERE team_id=?',(equipe,)).fetchone()[0]
   if count>=6:return await interaction.response.send_message('Équipe complète (6 joueurs).',ephemeral=True)
   other=con.execute('SELECT t.id FROM teams t JOIN team_members m ON t.id=m.team_id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,'fractures',membre.id)).fetchone()
   if other:return await interaction.response.send_message('Ce membre appartient déjà à une équipe.',ephemeral=True)
   con.execute('INSERT OR IGNORE INTO team_invitations(team_id,user_id,invited_by) VALUES(?,?,?)',(equipe,membre.id,interaction.user.id))
  await interaction.response.send_message(f'📨 Invitation enregistrée pour {membre.mention} dans l’équipe **#{equipe}**. Le membre doit accepter avec `/escape rejoindre`.',ephemeral=True)

 @app_commands.command(name='rejoindre',description='Accepter une invitation à rejoindre une équipe Escape Game.')
 @app_commands.describe(equipe='Numéro de l’équipe qui t’a invité')
 async def rejoindre(self,interaction:discord.Interaction,equipe:int):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  with db() as con:
   team=con.execute('SELECT adventure FROM teams WHERE id=? AND guild_id=?',(equipe,interaction.guild_id)).fetchone()
   invitation=con.execute('SELECT 1 FROM team_invitations WHERE team_id=? AND user_id=?',(equipe,interaction.user.id)).fetchone()
   if not team or not invitation:
    return await interaction.response.send_message('Aucune invitation valide pour cette équipe.',ephemeral=True)
   existing=con.execute('SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,team[0],interaction.user.id)).fetchone()
   if existing:
    return await interaction.response.send_message(f'Tu fais déjà partie de l’équipe #{existing[0]}.',ephemeral=True)
   count=con.execute('SELECT COUNT(*) FROM team_members WHERE team_id=?',(equipe,)).fetchone()[0]
   if count>=6: return await interaction.response.send_message('Cette équipe est complète.',ephemeral=True)
   con.execute('INSERT INTO team_members(team_id,user_id) VALUES(?,?)',(equipe,interaction.user.id))
   con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=?',(equipe,interaction.user.id))
  await interaction.response.send_message(f'✅ Tu as rejoint l’équipe **#{equipe}**.',ephemeral=True)

 @app_commands.command(name='refuser',description='Refuser une invitation à une équipe Escape Game.')
 @app_commands.describe(equipe='Numéro de l’équipe')
 async def refuser(self,interaction:discord.Interaction,equipe:int):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  with db() as con:
   removed=con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=? AND team_id IN (SELECT id FROM teams WHERE guild_id=?)',(equipe,interaction.user.id,interaction.guild_id)).rowcount
  await interaction.response.send_message('Invitation refusée.' if removed else 'Aucune invitation en attente.',ephemeral=True)

async def setup(bot): await bot.add_cog(EscapeGame(bot))
