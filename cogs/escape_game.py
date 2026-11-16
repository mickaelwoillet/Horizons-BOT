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
from escape_event_logs import log_escape_event

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
 ('📨・invitations', 'Invitations des équipes Escape Game'),
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

def leave_team(guild_id: int, user_id: int):
 """Remove one member without changing shared progress or other adventures.

 A captain with remaining teammates transfers leadership deterministically.
 The last captain cannot abandon an orphaned team or its saved game.
 """
 with db() as con:
  team=con.execute("""SELECT t.id,t.leader_id FROM teams t
       JOIN team_members m ON m.team_id=t.id
       WHERE t.guild_id=? AND t.adventure='fractures' AND m.user_id=?""",(guild_id,user_id)).fetchone()
  if not team: return 'none', None
  team_id, captain=team
  if captain==user_id:
   successor=con.execute('SELECT user_id FROM team_members WHERE team_id=? AND user_id<>? ORDER BY rowid LIMIT 1',(team_id,user_id)).fetchone()
   if successor is None: return 'last_captain',team_id
   con.execute('UPDATE teams SET leader_id=? WHERE id=?',(successor[0],team_id))
  con.execute('DELETE FROM team_members WHERE team_id=? AND user_id=?',(team_id,user_id))
  con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=?',(team_id,user_id))
  return ('captain_transferred' if captain==user_id else 'left'),team_id

class ConfirmTeamDeparture(discord.ui.View):
 def __init__(self, user_id:int):
  super().__init__(timeout=120)
  self.user_id=user_id
 @discord.ui.button(label='Confirmer mon départ',style=discord.ButtonStyle.danger,emoji='🚪')
 async def confirm(self,interaction:discord.Interaction,button:discord.ui.Button):
  if interaction.user.id!=self.user_id:
   return await interaction.response.send_message('Cette confirmation ne t’appartient pas.',ephemeral=True)
  status,team_id=leave_team(interaction.guild_id,interaction.user.id)
  if status=='last_captain':
   message='⚠️ Tu es le dernier membre et capitaine : ton départ est bloqué pour préserver la sauvegarde collective.'
  elif status=='none': message='Tu ne fais plus partie d’une équipe.'
  elif status=='captain_transferred': message=f'✅ Tu as quitté l’équipe **#{team_id}**. Le capitanat a été transmis à un membre restant.'
  else: message=f'✅ Tu as quitté l’équipe **#{team_id}**. Sa progression collective est conservée.'
  await interaction.response.edit_message(content=message,view=None)
 @discord.ui.button(label='Annuler',style=discord.ButtonStyle.secondary)
 async def cancel(self,interaction:discord.Interaction,button:discord.ui.Button):
  if interaction.user.id!=self.user_id:
   return await interaction.response.send_message('Cette confirmation ne t’appartient pas.',ephemeral=True)
  await interaction.response.edit_message(content='Départ annulé. Tu restes dans ton équipe.',view=None)

async def open_fractures(interaction:discord.Interaction,mode:str):
 if not interaction.guild:
  return await interaction.response.send_message('Commande disponible uniquement sur le serveur.', ephemeral=True)
 if not CONTENT_FILE.is_file():
  return await interaction.response.send_message('🔐 Cette aventure est encore en préparation.', ephemeral=True)
 try:
  content=load_adventure(CONTENT_FILE)
 except (ValueError,KeyError,OSError) as exc:
  return await interaction.response.send_message('⚠️ Le contenu de cette aventure est momentanément indisponible.', ephemeral=True)
 if mode=='solo':
  owner=interaction.user.id
 else:
  with db() as con:
   team=con.execute('SELECT t.id FROM teams t JOIN team_members m ON t.id=m.team_id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?', (interaction.guild_id,'fractures',interaction.user.id)).fetchone()
  if not team:
   return await interaction.response.send_message('Rejoins ou crée une équipe avant de jouer en collectif.', ephemeral=True)
  owner=team[0]
 engine=Engine(DB)
 previous = engine.status(interaction.guild_id, 'fractures', mode, owner)
 engine.start(interaction.guild_id,'fractures',mode,owner,content['rooms'][0]['id'])
 await show_room(interaction,engine,content,(interaction.guild_id,'fractures',mode,owner))
 if previous is None:
  await log_escape_event(interaction, 'start', mode=mode)


class RestartSoloConfirmation(discord.ui.View):
 def __init__(self, user_id: int):
  super().__init__(timeout=120)
  self.user_id = user_id

 @discord.ui.button(label='Confirmer : recommencer depuis la salle 1',style=discord.ButtonStyle.danger,emoji='🔄')
 async def confirm(self, interaction:discord.Interaction, button:discord.ui.Button):
  if interaction.user.id != self.user_id or not interaction.guild:
   return await interaction.response.send_message('Cette confirmation ne t’est pas destinée.',ephemeral=True)
  try:
   content = load_adventure(CONTENT_FILE)
   engine = Engine(DB)
   engine.restart_solo(interaction.guild_id,'fractures',self.user_id,content['rooms'][0]['id'])
   # Clear legacy solo records too; never touch team or other adventure data.
   with db() as con:
    con.execute('DELETE FROM progress WHERE guild_id=? AND user_id=? AND adventure=?',
                (interaction.guild_id,self.user_id,'fractures'))
    con.execute('DELETE FROM inventory WHERE guild_id=? AND mode=? AND owner_id=? AND adventure=?',
                (interaction.guild_id,'solo',self.user_id,'fractures'))
  except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
   return await interaction.response.send_message(f'⚠️ Impossible de recommencer : {exc}',ephemeral=True)
  for child in self.children: child.disabled = True
  await interaction.response.edit_message(content='🔄 Partie solo réinitialisée. Tu peux reprendre depuis la salle 1 avec `/escape jouer` (Solo).',view=self)

 @discord.ui.button(label='Annuler',style=discord.ButtonStyle.secondary)
 async def cancel(self,interaction:discord.Interaction,button:discord.ui.Button):
  if interaction.user.id != self.user_id:
   return await interaction.response.send_message('Cette confirmation ne t’est pas destinée.',ephemeral=True)
  await interaction.response.edit_message(content='Réinitialisation annulée : ta progression est conservée.',view=None)


class JoinTeamModal(discord.ui.Modal, title='Rejoindre une équipe'):
 team_number=discord.ui.TextInput(label="Numéro de l'équipe",placeholder="Exemple : 7",max_length=12)
 async def on_submit(self,interaction:discord.Interaction):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  try:
   team_id=int(str(self.team_number.value).strip())
   if team_id<=0: raise ValueError()
  except ValueError:
   return await interaction.response.send_message("Saisis un numéro d'équipe valide.",ephemeral=True)
  result=join_invited_team(interaction.guild_id,interaction.user.id,team_id)
  await interaction.response.send_message(result,ephemeral=True)

def join_invited_team(guild_id:int,user_id:int,team_id:int)->str:
 """Join only a team with a pending invitation, preserving collective progress."""
 with db() as con:
  team=con.execute('SELECT adventure FROM teams WHERE id=? AND guild_id=?',(team_id,guild_id)).fetchone()
  invitation=con.execute('SELECT 1 FROM team_invitations WHERE team_id=? AND user_id=?',(team_id,user_id)).fetchone()
  if not team or not invitation: return "Aucune invitation valide pour cette équipe."
  existing=con.execute('SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(guild_id,team[0],user_id)).fetchone()
  if existing: return f"Tu fais déjà partie de l’équipe #{existing[0]}."
  count=con.execute('SELECT COUNT(*) FROM team_members WHERE team_id=?',(team_id,)).fetchone()[0]
  if count>=6: return "Cette équipe est complète."
  con.execute('INSERT INTO team_members(team_id,user_id) VALUES(?,?)',(team_id,user_id))
  con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=?',(team_id,user_id))
 return f"✅ Tu as rejoint l’équipe **#{team_id}**. Tu peux ouvrir la partie avec « Créer une équipe » (qui reprend une équipe existante) ou `/escape jouer` en mode collectif."

def pending_invite(guild_id:int, team_id:int, user_id:int, captain_id:int)->str:
 """Store invitation only for the current captain, with membership checks."""
 with db() as con:
  team=con.execute("SELECT leader_id,adventure FROM teams WHERE id=? AND guild_id=?",(team_id,guild_id)).fetchone()
  if not team or team[0]!=captain_id or team[1]!='fractures':
   return 'Seul le capitaine de cette équipe peut inviter.'
  if user_id==captain_id:
   return 'Tu fais déjà partie de cette équipe.'
  if con.execute('SELECT 1 FROM team_members WHERE team_id=? AND user_id=?',(team_id,user_id)).fetchone():
   return 'Ce membre fait déjà partie de cette équipe.'
  if con.execute('SELECT 1 FROM teams t JOIN team_members m ON t.id=m.team_id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(guild_id,'fractures',user_id)).fetchone():
   return 'Ce membre appartient déjà à une équipe.'
  if con.execute('SELECT COUNT(*) FROM team_members WHERE team_id=?',(team_id,)).fetchone()[0]>=6:
   return 'Équipe complète (6 joueurs).'
  if con.execute('SELECT 1 FROM team_invitations WHERE team_id=? AND user_id=?',(team_id,user_id)).fetchone():
   return 'Une invitation est déjà en attente pour ce membre dans le salon Invitations.'
  con.execute('INSERT INTO team_invitations(team_id,user_id,invited_by) VALUES(?,?,?)',(team_id,user_id,captain_id))
 return 'ok'

def cancel_unpublished_invitation(guild_id:int,team_id:int,user_id:int):
 """Roll back an invitation that could not be published, so the captain can retry."""
 with db() as con:
  con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=? AND team_id IN (SELECT id FROM teams WHERE guild_id=?)', (team_id,user_id,guild_id))

class InvitationActions(discord.ui.View):
 def __init__(self,guild_id:int,team_id:int,invitee_id:int):
  super().__init__(timeout=None)
  self.guild_id,self.team_id,self.invitee_id=guild_id,team_id,invitee_id
  self.accept.custom_id=f'escape:invite:accept:{guild_id}:{team_id}:{invitee_id}'
  self.refuse.custom_id=f'escape:invite:refuse:{guild_id}:{team_id}:{invitee_id}'
 @discord.ui.button(label='Accepter',style=discord.ButtonStyle.success,emoji='✅')
 async def accept(self,interaction:discord.Interaction,button:discord.ui.Button):
  if interaction.user.id!=self.invitee_id or interaction.guild_id!=self.guild_id:
   return await interaction.response.send_message('Cette invitation ne t’est pas destinée.',ephemeral=True)
  message=join_invited_team(self.guild_id,self.invitee_id,self.team_id)
  if not message.startswith('✅'):
   return await interaction.response.send_message(message,ephemeral=True)
  await interaction.response.edit_message(content=f'{interaction.user.mention} — {message}',embed=None,view=None)
 @discord.ui.button(label='Refuser',style=discord.ButtonStyle.danger,emoji='✖️')
 async def refuse(self,interaction:discord.Interaction,button:discord.ui.Button):
  if interaction.user.id!=self.invitee_id or interaction.guild_id!=self.guild_id:
   return await interaction.response.send_message('Cette invitation ne t’est pas destinée.',ephemeral=True)
  with db() as con:
   removed=con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=? AND team_id IN (SELECT id FROM teams WHERE guild_id=?)',(self.team_id,self.invitee_id,self.guild_id)).rowcount
  await interaction.response.edit_message(content=(f'{interaction.user.mention} a refusé l’invitation.' if removed else 'Cette invitation n’est plus en attente.'),embed=None,view=None)

async def publish_team_invitation(guild,team_id,invitee_id):
 # Resolve the channel inside the Escape Game category, avoiding similarly named channels elsewhere.
 category=discord.utils.get(guild.categories,name=CATEGORY)
 channel=(discord.utils.get(category.text_channels,name='📨・invitations') if category else None)
 if channel is None: return None
 permissions=channel.permissions_for(guild.me)
 if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
  raise PermissionError('Permissions insuffisantes dans le salon Invitations (voir, écrire, intégrer des liens).')
 embed=emb('📨 Invitation — Les Fractures du Cosmos',
           f'<@{invitee_id}>, tu es invité(e) à rejoindre l’équipe **#{team_id}** !\n\n'
           'Seule la personne mentionnée peut répondre.')
 return await channel.send(content=f'<@{invitee_id}>',embed=embed,
      view=InvitationActions(guild.id,team_id,invitee_id),
      allowed_mentions=discord.AllowedMentions(users=True,roles=False,everyone=False))

class InviteMemberPicker(discord.ui.View):
 def __init__(self,guild_id:int,team_id:int,captain_id:int):
  super().__init__(timeout=180)
  self.guild_id,self.team_id,self.captain_id=guild_id,team_id,captain_id
  selector=discord.ui.UserSelect(placeholder='Choisis le membre à inviter',min_values=1,max_values=1)
  selector.callback=self.selected
  self.add_item(selector)
 async def selected(self,interaction:discord.Interaction):
  if interaction.user.id!=self.captain_id:
   return await interaction.response.send_message('Seul le capitaine peut utiliser ce menu.',ephemeral=True)
  member=self.children[0].values[0]
  if member.bot:
   return await interaction.response.send_message('Les bots ne peuvent pas rejoindre une équipe.',ephemeral=True)
  result=pending_invite(self.guild_id,self.team_id,member.id,self.captain_id)
  if result!='ok':
   return await interaction.response.send_message(result,ephemeral=True)
  try:
   posted=await publish_team_invitation(interaction.guild,self.team_id,member.id)
   if posted is None:
    cancel_unpublished_invitation(self.guild_id,self.team_id,member.id)
    notice='⚠️ Invitation non envoyée : salon 📨・invitations introuvable. Relance `/escape installer`, puis réessaie.'
   else:
    notice=f'📨 Invitation publiée dans {posted.channel.mention} pour {member.mention}.'
  except (discord.Forbidden,discord.HTTPException,PermissionError):
   cancel_unpublished_invitation(self.guild_id,self.team_id,member.id)
   notice='⚠️ Invitation non envoyée : permissions insuffisantes dans le salon Invitations. Tu pourras réessayer après correction.'
  await interaction.response.edit_message(content=notice,view=None)


class Portal(discord.ui.View):
 def __init__(self):
  super().__init__(timeout=None)
 @discord.ui.button(label='Jouer en solo',style=discord.ButtonStyle.primary,emoji='🌌',custom_id='escape:solo')
 async def solo(self,interaction:discord.Interaction,button:discord.ui.Button):
  await open_fractures(interaction,'solo')
 @discord.ui.button(label='Créer une équipe',style=discord.ButtonStyle.secondary,emoji='👥',custom_id='escape:team')
 async def team(self,interaction:discord.Interaction,button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  created_id=None
  with db() as con:
   current=con.execute('SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,'fractures',interaction.user.id)).fetchone()
   if not current:
    cur=con.execute('INSERT INTO teams(guild_id,adventure,leader_id) VALUES(?,?,?)',(interaction.guild_id,'fractures',interaction.user.id))
    created_id=cur.lastrowid
    con.execute('INSERT INTO team_members(team_id,user_id) VALUES(?,?)',(created_id,interaction.user.id))
  await open_fractures(interaction,'team')
  if created_id is not None:
   await interaction.followup.send(f'👥 Équipe **#{created_id}** créée ! Invite des partenaires avec `/escape inviter` (six joueurs maximum).',ephemeral=True)
 @discord.ui.button(label='Inviter un membre',style=discord.ButtonStyle.secondary,emoji='📨',custom_id='escape:invite_member')
 async def invite_member(self,interaction:discord.Interaction,button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  with db() as con:
   team=con.execute("SELECT id FROM teams WHERE guild_id=? AND adventure='fractures' AND leader_id=?",(interaction.guild_id,interaction.user.id)).fetchone()
  if not team:
   return await interaction.response.send_message('Crée une équipe ou deviens capitaine pour inviter un membre.',ephemeral=True)
  await interaction.response.send_message(f'📨 **Inviter dans l’équipe #{team[0]}** : sélectionne un membre.',view=InviteMemberPicker(interaction.guild_id,team[0],interaction.user.id),ephemeral=True)
 @discord.ui.button(label='Rejoindre une équipe',style=discord.ButtonStyle.secondary,emoji='🤝',custom_id='escape:join_team')
 async def join_team(self,interaction:discord.Interaction,button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  await interaction.response.send_modal(JoinTeamModal())
 @discord.ui.button(label='Quitter mon équipe',style=discord.ButtonStyle.secondary,emoji='🚪',custom_id='escape:leave_team')
 async def leave(self,interaction:discord.Interaction,button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  with db() as con:
   team=con.execute("SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure='fractures' AND m.user_id=?",(interaction.guild_id,interaction.user.id)).fetchone()
  if not team:
   return await interaction.response.send_message('Tu ne fais partie d’aucune équipe Escape Game.',ephemeral=True)
  await interaction.response.send_message(f'⚠️ Confirmer ton départ de l’équipe **#{team[0]}** ? La progression collective restera sauvegardée.',view=ConfirmTeamDeparture(interaction.user.id),ephemeral=True)
 @discord.ui.button(label='Recommencer en solo',style=discord.ButtonStyle.secondary,emoji='🔄',custom_id='escape:restart_solo')
 async def restart_solo_button(self,interaction:discord.Interaction,button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  await interaction.response.send_message(
   '⚠️ **Recommencer ton aventure solo depuis la salle 1 ?** '
   'Cette action efface uniquement tes énigmes, objets et indices de l’Escape Game solo. '
   'Les autres joueurs, les équipes, NOX et NOX Junior ne seront pas affectés.',
   view=RestartSoloConfirmation(interaction.user.id),ephemeral=True)

 @discord.ui.button(label='Ma progression',style=discord.ButtonStyle.secondary,emoji='💾',custom_id='escape:progress')
 async def progress(self, interaction:discord.Interaction, button:discord.ui.Button):
  if not interaction.guild:
   return await interaction.response.send_message('Disponible uniquement sur le serveur.',ephemeral=True)
  with db() as con:
   team=con.execute('SELECT t.id,t.room FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure=? AND m.user_id=?',(interaction.guild_id,'fractures',interaction.user.id)).fetchone()
  engine = Engine(DB)
  solo_state = engine.status(interaction.guild_id, 'fractures', 'solo', interaction.user.id)
  team_state = engine.status(interaction.guild_id, 'fractures', 'team', team[0]) if team else None
  solo_room = solo_state.get('room_id', 'inconnue') if solo_state else 'pas encore commencé'
  team_room = team_state.get('room_id', 'inconnue') if team_state else 'équipe créée' if team else 'aucune'
  team_label = f'#{team[0]} — {team_room}' if team else team_room
  msg = (f'💾 **Ta progression sauvegardée**\n'
         f'**Solo :** {solo_room}\n'
         f'**Collectif :** {team_label}\n\n'
         '🔄 Pour retrouver des boutons actifs après une pause ou un redémarrage, '
         'utilise `/escape jouer` et sélectionne le même mode. '
         'Les anciennes interfaces expirées ne peuvent pas être réactivées.')
  await interaction.response.send_message(msg, ephemeral=True)

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
 @app_commands.choices(mode=[app_commands.Choice(name='Solo',value='solo'),app_commands.Choice(name='Collectif',value='team')])
 async def jouer(self,interaction:discord.Interaction,mode:app_commands.Choice[str]):
  await open_fractures(interaction,mode.value)

 @app_commands.command(name='recommencer',description='Recommencer ton aventure solo depuis la salle 1 après confirmation.')
 async def recommencer(self,interaction:discord.Interaction):
  if not interaction.guild:
   return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  if not CONTENT_FILE.is_file():
   return await interaction.response.send_message('Aventure momentanément indisponible.',ephemeral=True)
  await interaction.response.send_message(
   '⚠️ **Recommencer l’aventure solo ?** Toutes tes énigmes résolues, tes objets et tes indices Escape Game solo seront effacés. '
   'Ta progression collective, les autres joueurs, NOX et NOX Junior ne seront pas modifiés.',
   view=RestartSoloConfirmation(interaction.user.id),ephemeral=True)

 @app_commands.command(name='installer',description='Installer la catégorie Escape Game et ses six salons (administration).')
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
     CHANNELS[1][0]:(emb('🌌 Les Fractures du Cosmos','Il fut un temps où les étoiles veillaient sur les mondes, où chaque constellation avait sa place et où le Cosmos semblait éternel.\n\nPuis, une nuit, **quelque chose s’est brisé.**\n\nSans avertissement, des étoiles ont disparu. Des fragments de réalité se sont détachés du ciel. Des lieux oubliés, prisonniers du temps, ont commencé à réapparaître…\n\nPersonne ne sait ce qui a provoqué cette catastrophe. Un accident ? Une expérience interdite ? Ou une volonté ancienne, réveillée après des millénaires de silence ?\n\nAu milieu du chaos, un mystérieux signal émane d’un observatoire abandonné.\n\nEt dans les profondeurs de ce signal, un nom revient sans cesse…\n\n**NOX.**\n\nPourquoi ce nom ? Que cache l’observatoire ? Et surtout… que se passera-t-il lorsque la dernière étoile s’éteindra ?\n\n**Treize salles. Des énigmes, des secrets et des choix qui pourraient changer le destin de l’univers.**\n\n**Le Cosmos attend ses sauveurs. Oserez-vous franchir la première porte ?**\n\nChoisis ton mode avec les boutons ci-dessous. Tu peux aussi rejoindre une équipe qui t’a invité.\n\n🔎 Clique sur l’image pour l’agrandir.'),Portal()),
     CHANNELS[2][0]:(emb('🏚️ Le Manoir des Murmures','Une demeure, des secrets et des voix qui ne devraient plus résonner.\n\n**À venir prochainement.**'),None),
     CHANNELS[3][0]:(emb('🌊 La Cité Engloutie','Sous les eaux sommeille une civilisation oubliée.\n\n**À venir prochainement.**'),None),
     CHANNELS[4][0]:(emb('🧩 Entraide Escape Game','Trouvez vos partenaires et partagez vos théories !\n\n**Pas de spoilers :** évitez les réponses, codes et captures révélant les solutions.'),None),
     CHANNELS[5][0]:(emb('📨 Invitations aux équipes','Les invitations aux équipes sont publiées ici avec un ping. Seul le membre mentionné peut accepter ou refuser grâce aux boutons.'),None),
    }
    messages=gs.setdefault('messages',{})
    for name,(embed,view) in panels.items():
     channel=guild.get_channel(channels[name]);message=None
     mid=messages.get(name)
     if mid:
      try: message=await channel.fetch_message(mid)
      except (discord.NotFound, discord.Forbidden, discord.HTTPException): pass
     # A missing stored ID may occur after a migration; search existing bot panels
     # before posting another message. Never delete user messages or invitations.
     if message is None:
      try:
       async for old in channel.history(limit=200):
        if self.bot.user and old.author.id==self.bot.user.id and old.embeds and old.embeds[0].title==embed.title:
         message=old;break
      except (discord.Forbidden, discord.HTTPException):
       pass
     channel_perms=channel.permissions_for(bot_member)
     if not (channel_perms.view_channel and channel_perms.send_messages and channel_perms.embed_links):
      raise PermissionError(f'Permissions insuffisantes dans {channel.name} : voir, envoyer et intégrer des liens.')
     if message: await message.edit(embed=embed,view=view)
     else: message=await channel.send(embed=embed,view=view)
     messages[name]=message.id
     save_installation(state)
    save_installation(state)
    await interaction.followup.send(f'✅ Espace Escape Game installé : **{len(created)} nouveaux salons**, **{len(CHANNELS)} panneaux vérifiés**. Le portail des Fractures du Cosmos est configuré.',ephemeral=True)
   except (discord.HTTPException, PermissionError) as exc:
    save_installation(state)
    await interaction.followup.send(f'⚠️ Installation interrompue : {exc}. Relance `/escape installer` après correction ; les éléments existants seront réutilisés.',ephemeral=True)
 @app_commands.command(name='inviter',description='Inviter un membre dans son équipe Escape Game (maximum 6).')
 @app_commands.describe(equipe='Numéro de ton équipe',membre='Membre à inviter')
 async def inviter(self,interaction:discord.Interaction,equipe:int,membre:discord.Member):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  if membre.bot: return await interaction.response.send_message('Les bots ne peuvent pas rejoindre une équipe.',ephemeral=True)
  result=pending_invite(interaction.guild_id,equipe,membre.id,interaction.user.id)
  if result!='ok':
   return await interaction.response.send_message(result,ephemeral=True)
  try:
   posted=await publish_team_invitation(interaction.guild,equipe,membre.id)
   if posted is None:
    cancel_unpublished_invitation(interaction.guild_id,equipe,membre.id)
    message='⚠️ Invitation non envoyée : salon 📨・invitations introuvable. Relance `/escape installer`, puis réessaie.'
   else:
    message=f'📨 Invitation publiée dans {posted.channel.mention} pour {membre.mention}.'
  except (discord.Forbidden,discord.HTTPException,PermissionError):
   cancel_unpublished_invitation(interaction.guild_id,equipe,membre.id)
   message='⚠️ Invitation non envoyée : permissions insuffisantes dans le salon Invitations. Tu pourras réessayer après correction.'
  await interaction.response.send_message(message,ephemeral=True)

 @app_commands.command(name='rejoindre',description='Accepter une invitation à rejoindre une équipe Escape Game.')
 @app_commands.describe(equipe='Numéro de l’équipe qui t’a invité')
 async def rejoindre(self,interaction:discord.Interaction,equipe:int):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  await interaction.response.send_message(join_invited_team(interaction.guild_id,interaction.user.id,equipe),ephemeral=True)

 @app_commands.command(name='quitter',description='Quitter ton équipe Escape Game après confirmation.')
 async def quitter(self,interaction:discord.Interaction):
  if not interaction.guild:
   return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  with db() as con:
   team=con.execute("SELECT t.id FROM teams t JOIN team_members m ON m.team_id=t.id WHERE t.guild_id=? AND t.adventure='fractures' AND m.user_id=?",(interaction.guild_id,interaction.user.id)).fetchone()
  if not team:
   return await interaction.response.send_message('Tu ne fais partie d’aucune équipe Escape Game.',ephemeral=True)
  await interaction.response.send_message(f'⚠️ Quitter l’équipe **#{team[0]}** ? Tu perdras l’accès à sa progression, mais sa sauvegarde restera intacte.',view=ConfirmTeamDeparture(interaction.user.id),ephemeral=True)

 @app_commands.command(name='refuser',description='Refuser une invitation à une équipe Escape Game.')
 @app_commands.describe(equipe='Numéro de l’équipe')
 async def refuser(self,interaction:discord.Interaction,equipe:int):
  if not interaction.guild: return await interaction.response.send_message('Commande réservée au serveur.',ephemeral=True)
  with db() as con:
   removed=con.execute('DELETE FROM team_invitations WHERE team_id=? AND user_id=? AND team_id IN (SELECT id FROM teams WHERE guild_id=?)',(equipe,interaction.user.id,interaction.guild_id)).rowcount
  await interaction.response.send_message('Invitation refusée.' if removed else 'Aucune invitation en attente.',ephemeral=True)

async def setup(bot):
 await bot.add_cog(EscapeGame(bot))
 try:
  with db() as con:
   invitations=con.execute('SELECT t.guild_id,i.team_id,i.user_id FROM team_invitations i JOIN teams t ON t.id=i.team_id').fetchall()
 except sqlite3.Error as exc:
  print(f'[ESCAPE] Impossible de restaurer les invitations en attente : {exc}')
  return
 restored=0
 for guild_id,team_id,user_id in invitations:
  bot.add_view(InvitationActions(guild_id,team_id,user_id))
  restored+=1
 print(f'[ESCAPE] {restored} invitation(s) persistante(s) restaurée(s).')

