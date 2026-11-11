"""NOX Junior V0.1: private adoption and care interface."""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR
from pathlib import Path
import io
import json
import logging
from PIL import Image, ImageDraw, ImageFont
from . import nox_junior_engine as engine
from . import nox_refuge_engine
from . import nox_junior_visual
from . import nox_junior_complicite as complicite
from . import nox_junior_aventures as aventures
from . import nox_junior_personnalite as personnalite

FOUNDER_ROLE = 1566561887305339001
LIEN_VIVANT_ROLE = 1567215752656715927
DB = Path(DATA_DIR) / 'nox_junior.sqlite3'
REFUGE_DB = Path(DATA_DIR) / 'nox_refuge.sqlite3'
GIVEAWAY_CHANNEL_ID = 1566562183490441326
INVITE_IMAGE = Path(__file__).resolve().parent.parent / 'assets' / 'nox_junior' / 'invitation_grand_nox.png'
log = logging.getLogger(__name__)


def eligible(member, guild_id):
    if not any(r.id == LIEN_VIVANT_ROLE for r in member.roles):
        return False, 0
    with nox_refuge_engine.connect(REFUGE_DB) as con:
        count = engine.care_count(con, guild_id, member.id)
    return count >= 10, count


class AdoptionModal(discord.ui.Modal, title='Adopter un NOX Junior'):
    name = discord.ui.TextInput(label='Prénom de ton compagnon', min_length=2, max_length=24)

    def __init__(self, color):
        super().__init__()
        self.color = color

    async def on_submit(self, interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message('Uniquement sur HORIZONS.', ephemeral=True)
        ok, count = eligible(interaction.user, interaction.guild.id)
        with engine.connect(DB) as con:
            grant = con.execute('SELECT 1 FROM junior_grants WHERE guild_id=? AND owner_id=?',(interaction.guild.id,interaction.user.id)).fetchone()
            existing = engine.pets(con,interaction.guild.id,interaction.user.id)
            if grant and len(existing)==1:
                ok = True
            try:
                pet_id = engine.adopt(con, interaction.guild.id, interaction.user.id, str(self.name), self.color, ok)
            except engine.JuniorError as exc:
                return await interaction.response.send_message(f'🐣 {exc} (Soins collectifs : {count}/10)', ephemeral=True)
        with engine.connect(DB) as con:
            init_invitation_table(con)
            con.execute("UPDATE junior_egg_invitations SET status='adopted' WHERE guild_id=? AND owner_id=? AND status='pending'", (interaction.guild.id, interaction.user.id))
        await interaction.response.send_message(f'🐣 Bienvenue à **{discord.utils.escape_markdown(str(self.name))}** ! Ton œuf {self.color} (n°{pet_id}) est prêt. Ouvre `/monnox` pour le retrouver.', ephemeral=True)


class ColorSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='Choisis la couleur de ton œuf', options=[discord.SelectOption(label=('🌈 Arc-en-ciel' if c == 'arc_en_ciel' else c.capitalize()), value=c) for c in engine.COLORS])

    async def callback(self, interaction):
        await interaction.response.send_modal(AdoptionModal(self.values[0]))


class AdoptionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ColorSelect())


class RenameModal(discord.ui.Modal, title='Renommer mon NOX'):
    name = discord.ui.TextInput(label='Nouveau prénom', min_length=2, max_length=24)

    def __init__(self, pet_id):
        super().__init__()
        self.pet_id = pet_id

    async def on_submit(self, interaction):
        with engine.connect(DB) as con:
            try:
                engine.rename(con, self.pet_id, interaction.user.id, str(self.name))
            except engine.JuniorError as exc:
                return await interaction.response.send_message(str(exc), ephemeral=True)
        await interaction.response.send_message('✨ Prénom modifié !', ephemeral=True)


class PetSelect(discord.ui.Select):
    def __init__(self, rows):
        super().__init__(placeholder='Choisis ton compagnon', options=[discord.SelectOption(label=f"{r['name']} · {r['color']}", value=str(r['id'])) for r in rows])

    async def callback(self, interaction):
        with engine.connect(DB) as con:
            try:
                row = engine.snapshot(con, int(self.values[0]), interaction.user.id, interaction.guild.id)
            except engine.JuniorError as exc:
                return await interaction.response.send_message(str(exc), ephemeral=True)
        with engine.connect(DB) as con:
            purse = engine.wallet(con,row['id'],interaction.user.id,interaction.guild.id)
            picture = room_picture(con,row['id'],interaction.user.id,interaction.guild.id,row)
        await interaction.response.send_message(embed=visual_embed(row,purse),file=picture,view=PetView(row['id']),ephemeral=True)


def pet_embed(row):
    stage, days = engine.stage(row)
    state, description = engine.mood(row)
    embed = discord.Embed(title=f"🐣 {discord.utils.escape_markdown(row['name'])} · {('🌈 Arc-en-ciel' if row['color'] == 'arc_en_ciel' else row['color'].capitalize())}", description=f"{description}\n\n**Stade :** {stage.replace('_',' ')} · **Âge :** {days} jour(s)\n**Complicité :** {row['bond']} · **Activités :** {row['activities']}", color=0x7864CC)
    for stat, label, icon in [('satiete','Satiété','🍎'),('hydratation','Hydratation','💧'),('bonheur','Bonheur','💜'),('energie','Énergie','⚡'),('hygiene','Hygiène','🫧')]:
        value = max(0, min(100, round(row[stat])))
        embed.add_field(name=f'{icon} {label}', value=f"{'▰' * (value // 10)}{'▱' * (10-value // 10)}  {value}/100", inline=False)
    embed.set_footer(text='NOX Junior V1.0 · Panneau personnel privé')
    return embed


def visual_embed(row, purse=None, reaction=None):
    """Immersive room panel with compact readable gauges and one large picture."""
    embed = pet_embed(row)
    stage, days = engine.stage(row)
    mood, description = engine.mood(row)
    lines = []
    for key, label, icon in [('satiete','Faim','🍎'),('hydratation','Soif','💧'),
                             ('bonheur','Bonheur','💜'),('energie','Énergie','⚡'),('hygiene','Hygiène','🫧')]:
        value = max(0, min(100, round(row[key])))
        lines.append(f'{icon} **{label}**  {"▰" * (value//10)}{"▱" * (10-value//10)}  {value}%')
    embed.clear_fields()
    embed.description = (f'**{stage.replace("_", " ").capitalize()} · Jour {days}**  ·  {description}'
                         + (f'\n✨ **{purse["balance"]}** poussières d’étoiles' if purse else '')
                         + ('\n\n' + reaction if reaction else ''))
    embed.add_field(name='💜 Les besoins de NOX',value='\n'.join(lines),inline=False)
    embed.set_image(url='attachment://nox_junior_chambre.png')
    embed.set_footer(text='HORIZONS · NOX Junior · Compagnon personnel')
    return embed


def room_picture(con, pet_id, owner_id, guild_id, row, mood_override=None):
    info = engine.room(con,pet_id,owner_id,guild_id)
    stage, _ = engine.stage(row)
    mood, _ = engine.mood(row)
    return discord.File(nox_junior_visual.compose_room(
        dict(row),stage=stage,mood=mood_override or mood,theme=info['theme'],decorations=info['slots']),
        filename='nox_junior_chambre.png')


class PetListView(discord.ui.View):
    def __init__(self, rows, can_adopt=False):
        super().__init__(timeout=180)
        self.add_item(PetSelect(rows))
        if not can_adopt:
            self.remove_item(self.adopt_button)

    @discord.ui.button(label='Adopter un autre NOX',emoji='🥚',style=discord.ButtonStyle.success)
    async def adopt_button(self,interaction,button):
        await interaction.response.send_message('Choisis une couleur pour ton nouvel œuf :',view=AdoptionView(),ephemeral=True)


PALETTE = nox_junior_visual.PALETTE


def baby_portrait(row, room=None):
    """Stage-aware illustration using the independent visual engine."""
    stage, _ = engine.stage(row)
    mood, _ = engine.mood(row)
    room = room or {'theme':None,'decoration':'none'}
    return nox_junior_visual.compose_room(dict(row), stage=stage, mood=mood,
        theme=room.get('theme'), decorations=room.get('slots',{}))


class GameView(discord.ui.View):
    def __init__(self,pet_id,session,owner_id):
        super().__init__(timeout=300)
        self.pet_id,self.session,self.owner_id=pet_id,session,owner_id
        for index,label in enumerate(session['choices']):
            button=discord.ui.Button(label=label[:80],style=discord.ButtonStyle.secondary,custom_id=f'junior_game:{session["token"]}:{index}')
            async def respond(interaction, i=index):
                if interaction.user.id!=self.owner_id:
                    return await interaction.response.send_message('Cette partie ne t’appartient pas.',ephemeral=True)
                try:
                    with engine.connect(DB) as con:
                        success,bond=engine.game_finish(con,self.session['token'],self.pet_id,interaction.user.id,interaction.guild.id,str(i))
                except engine.JuniorError as exc:
                    return await interaction.response.send_message(str(exc),ephemeral=True)
                await interaction.response.edit_message(content=('✨ Bravo !' if success else '💙 Bien essayé !')+f' Complicité +{bond}.',embed=None,view=None)
                self.stop()
            button.callback=respond
            self.add_item(button)


class GamesMenu(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.pet_id,self.owner_id=pet_id,owner_id
    async def launch(self,interaction,game):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Ce NOX ne t’appartient pas.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                session=engine.game_start(con,self.pet_id,interaction.user.id,interaction.guild.id,game)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        await interaction.response.edit_message(content=session['question'],view=GameView(self.pet_id,session,self.owner_id))
    @discord.ui.button(label='Chasse aux étoiles',emoji='⭐')
    async def stars(self,interaction,button): await self.launch(interaction,'etoiles')
    @discord.ui.button(label='Mémoire cosmique',emoji='🌙')
    async def memory(self,interaction,button): await self.launch(interaction,'memoire')
    @discord.ui.button(label='Décision cosmique',emoji='🧭')
    async def choices(self,interaction,button): await self.launch(interaction,'choix')
    @discord.ui.button(label='Cristaux mystérieux',emoji='💎',row=1)
    async def crystals(self,interaction,button): await self.launch(interaction,'cristaux')
    @discord.ui.button(label='Énigmes stellaires',emoji='🧩',row=1)
    async def riddles(self,interaction,button): await self.launch(interaction,'enigmes')
    @discord.ui.button(label='Constellations',emoji='🌌',row=1)
    async def constellations(self,interaction,button): await self.launch(interaction,'constellations')
    @discord.ui.button(label='Parcours cosmique',emoji='🏃',row=2)
    async def course(self,interaction,button): await self.launch(interaction,'parcours')
    @discord.ui.button(label='Course des comètes',emoji='☄️',row=2)
    async def comets(self,interaction,button): await self.launch(interaction,'cometes')
    @discord.ui.button(label='Mission sauvetage',emoji='🛟',row=2)
    async def rescue(self,interaction,button): await self.launch(interaction,'sauvetage')


    @discord.ui.button(label='Cache-cache cosmique',emoji='🙈',row=3)
    async def hide_and_seek(self,interaction,button): await self.launch(interaction,'cache_cache')
    @discord.ui.button(label='Cuisine des étoiles',emoji='🧁',row=3)
    async def cooking(self,interaction,button): await self.launch(interaction,'cuisine')
    @discord.ui.button(label='Danse des constellations',emoji='💃',row=3)
    async def dancing(self,interaction,button): await self.launch(interaction,'danse')


class NoteModal(discord.ui.Modal):
    def __init__(self, pet_id, owner_id, note=None):
        super().__init__(title='✍️ Modifier ma note' if note else '✍️ Nouvelle note de NOX')
        self.pet_id, self.owner_id, self.note_id = pet_id, owner_id, note['id'] if note else None
        self.note_title = discord.ui.TextInput(label='Titre', max_length=80, required=True,
            default=note['title'] if note else None)
        self.note_body = discord.ui.TextInput(label='Mon souvenir', style=discord.TextStyle.paragraph,
            max_length=1000, required=True, default=note['body'] if note else None)
        self.add_item(self.note_title)
        self.add_item(self.note_body)

    async def on_submit(self, interaction):
        if interaction.user.id != self.owner_id or interaction.guild is None:
            return await interaction.response.send_message('Accès refusé.', ephemeral=True)
        try:
            with engine.connect(DB) as con:
                if self.note_id is None:
                    engine.note_create(con, self.pet_id, self.owner_id, interaction.guild.id,
                                       str(self.note_title), str(self.note_body))
                else:
                    engine.note_edit(con, self.note_id, self.pet_id, self.owner_id, interaction.guild.id,
                                     str(self.note_title), str(self.note_body))
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc), ephemeral=True)
        await interaction.response.send_message('📖 Note enregistrée dans le journal privé de ton NOX.', ephemeral=True)


class NoteActions(discord.ui.View):
    def __init__(self, pet_id, owner_id, note_id):
        super().__init__(timeout=180)
        self.pet_id, self.owner_id, self.note_id = pet_id, owner_id, note_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id or interaction.guild is None:
            await interaction.response.send_message('Accès refusé.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Modifier', emoji='✏️', style=discord.ButtonStyle.secondary)
    async def edit(self, interaction, button):
        try:
            with engine.connect(DB) as con:
                note = engine.note_get(con,self.note_id,self.pet_id,self.owner_id,interaction.guild.id)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc), ephemeral=True)
        await interaction.response.send_modal(NoteModal(self.pet_id,self.owner_id,note))

    @discord.ui.button(label='Supprimer', emoji='🗑️', style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        await interaction.response.send_message('Supprimer définitivement cette note ?',
            view=NoteDeleteConfirm(self.pet_id,self.owner_id,self.note_id), ephemeral=True)

    @discord.ui.button(label='Partager', emoji='📢', style=discord.ButtonStyle.primary)
    async def share(self, interaction, button):
        await interaction.response.send_message('Publier cette note dans le salon actuel ? Elle sera visible par tous.',
            view=NoteShareConfirm(self.pet_id,self.owner_id,self.note_id,interaction.channel_id), ephemeral=True)


class NoteDeleteConfirm(discord.ui.View):
    def __init__(self, pet_id, owner_id, note_id):
        super().__init__(timeout=90)
        self.pet_id,self.owner_id,self.note_id=pet_id,owner_id,note_id

    @discord.ui.button(label='Confirmer la suppression',style=discord.ButtonStyle.danger)
    async def confirm(self,interaction,button):
        if interaction.user.id!=self.owner_id or interaction.guild is None:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                engine.note_delete(con,self.note_id,self.pet_id,self.owner_id,interaction.guild.id)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        await interaction.response.edit_message(content='🗑️ Note supprimée.',view=None)
        self.stop()

    @discord.ui.button(label='Annuler',style=discord.ButtonStyle.secondary)
    async def cancel(self,interaction,button):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        await interaction.response.edit_message(content='Suppression annulée.',view=None)
        self.stop()


class NoteShareConfirm(discord.ui.View):
    def __init__(self, pet_id, owner_id, note_id, channel_id):
        super().__init__(timeout=90)
        self.pet_id,self.owner_id,self.note_id,self.channel_id=pet_id,owner_id,note_id,channel_id

    @discord.ui.button(label='Publier cette note',style=discord.ButtonStyle.primary)
    async def confirm(self,interaction,button):
        if interaction.user.id!=self.owner_id or interaction.guild is None or interaction.channel_id!=self.channel_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                note=engine.note_get(con,self.note_id,self.pet_id,self.owner_id,interaction.guild.id)
                pet=engine.snapshot(con,self.pet_id,self.owner_id,interaction.guild.id)
            embed=discord.Embed(title='📖 '+discord.utils.escape_markdown(discord.utils.escape_mentions(note['title'])),
                description=discord.utils.escape_mentions(note['body']),color=0x7864CC)
            embed.set_footer(text=f'Un souvenir de {pet["name"]} · Journal NOX Junior')
            await interaction.response.defer(ephemeral=True)
            await interaction.channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
            await interaction.followup.send('📢 Ta note a été partagée.',ephemeral=True)
        except (engine.JuniorError,discord.Forbidden,discord.HTTPException) as exc:
            if not interaction.response.is_done():
                await interaction.response.send_message(f'Publication impossible : {exc}',ephemeral=True)
            else:
                await interaction.followup.send(f'Publication impossible : {exc}',ephemeral=True)
        self.stop()

    @discord.ui.button(label='Annuler',style=discord.ButtonStyle.secondary)
    async def cancel(self,interaction,button):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        await interaction.response.edit_message(content='Partage annulé.',view=None)
        self.stop()


class NoteSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id,notes):
        self.pet_id,self.owner_id=pet_id,owner_id
        super().__init__(placeholder='Choisir une note',options=[discord.SelectOption(
            label=n['title'][:100],value=str(n['id']),description=f'Note n°{n["id"]}') for n in notes])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id or interaction.guild is None:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                note=engine.note_get(con,int(self.values[0]),self.pet_id,self.owner_id,interaction.guild.id)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        embed=discord.Embed(title='📖 '+discord.utils.escape_markdown(discord.utils.escape_mentions(note['title'])),
            description=discord.utils.escape_mentions(note['body']),color=0x7864CC)
        await interaction.response.send_message(embed=embed,
            view=NoteActions(self.pet_id,self.owner_id,note['id']),ephemeral=True)


class JournalView(discord.ui.View):
    def __init__(self,pet_id,owner_id,notes):
        super().__init__(timeout=180)
        self.pet_id,self.owner_id=pet_id,owner_id
        if notes:
            self.add_item(NoteSelect(pet_id,owner_id,notes))

    @discord.ui.button(label='Écrire une note',emoji='✍️',style=discord.ButtonStyle.primary,row=1)
    async def create(self,interaction,button):
        if interaction.user.id!=self.owner_id or interaction.guild is None:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        await interaction.response.send_modal(NoteModal(self.pet_id,self.owner_id))


class ExplorationView(discord.ui.View):
    def __init__(self,pet_id,owner_id,session):
        super().__init__(timeout=600)
        self.pet_id,self.owner_id,self.session=pet_id,owner_id,session
        for index,label in enumerate(session['choices']):
            button=discord.ui.Button(label=label[:80],style=discord.ButtonStyle.secondary)
            async def respond(interaction,i=index):
                if interaction.user.id!=self.owner_id:
                    return await interaction.response.send_message('Cette exploration ne t’appartient pas.',ephemeral=True)
                try:
                    with engine.connect(DB) as con:
                        result=engine.exploration_step(con,self.session['token'],self.pet_id,self.owner_id,interaction.guild.id,str(i))
                except engine.JuniorError as exc:
                    return await interaction.response.send_message(str(exc),ephemeral=True)
                if result['finished']:
                    await interaction.response.edit_message(content=f'✨ **{result["title"]}**\nDécouverte : **{discord.utils.escape_markdown(result["discovery"])}** '+('🆕' if result['new'] else '(déjà connue)')+'\n💜 Complicité +3. Consulte ton carnet de découvertes !',view=None)
                    self.stop()
                else:
                    result['token']=self.session['token']
                    await interaction.response.edit_message(content=result['question'],view=ExplorationView(self.pet_id,self.owner_id,result))
                    self.stop()
            button.callback=respond
            self.add_item(button)


class RegionSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id):
        self.pet_id,self.owner_id=pet_id,owner_id
        super().__init__(placeholder='Choisir une région',options=[discord.SelectOption(label=title,value=key) for key,(title,_,_) in engine.REGIONS.items()])
    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Ce NOX ne t’appartient pas.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                session=engine.exploration_start(con,self.pet_id,self.owner_id,interaction.guild.id,self.values[0])
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        await interaction.response.edit_message(content=f'**{session["title"]}**\n{session["question"]}',view=ExplorationView(self.pet_id,self.owner_id,session))


class ExplorationMenu(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.pet_id,self.owner_id=pet_id,owner_id
        self.add_item(RegionSelect(pet_id,owner_id))

    @discord.ui.button(label='Promenades libres',emoji='🚶',style=discord.ButtonStyle.primary,row=1)
    async def walk(self,interaction,button):
        await interaction.response.edit_message(content='🚶 Choisis une promenade avec NOX. Rejouable, même pendant le repos, sans récompense économique.',view=PromenadeMenu(self.pet_id,self.owner_id))


def promenade_embed(session, completed=False, reaction=''):
    title = aventures.WALKS[session['code']][0]
    description = session['text']
    if completed:
        description += '\n📸 **Souvenir enregistré dans ton album !**'
    if reaction:
        description += '\n' + reaction
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    embed.set_image(url='attachment://promenade.png')
    embed.set_footer(text='Promenade libre · rejouable · sans récompense économique')
    return embed

class PromenadeScene(discord.ui.View):
    def __init__(self,pet_id,owner_id,session):
        super().__init__(timeout=600)
        self.pet_id,self.owner_id,self.session=pet_id,owner_id,session
        for index,label in enumerate(aventures.choices(session)):
            button=discord.ui.Button(label=label[:80],style=discord.ButtonStyle.secondary)
            async def respond(interaction,i=index):
                if interaction.user.id!=self.owner_id or interaction.guild is None:
                    return await interaction.response.send_message('Cette promenade ne t’appartient pas.',ephemeral=True)
                try:
                    result=aventures.advance(self.session,i)
                except ValueError as exc:
                    return await interaction.response.send_message(str(exc),ephemeral=True)
                if result['done']:
                    with engine.connect(DB) as con:
                        engine.walk_memory_add(con,self.pet_id,self.owner_id,interaction.guild.id,result['code'],result['souvenir'])
                        personnalite.record(con,self.pet_id,'promenade:'+result['code'])
                        reaction = personnalite.reaction(personnalite.profile(con,self.pet_id), 'promenade')
                    await interaction.response.edit_message(content=None,embed=promenade_embed(result,True,reaction),view=None)
                else:
                    await interaction.response.edit_message(content=None,embed=promenade_embed(result),view=PromenadeScene(self.pet_id,self.owner_id,result))
                self.stop()
            button.callback=respond
            self.add_item(button)


class PromenadeSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id):
        self.pet_id,self.owner_id=pet_id,owner_id
        super().__init__(placeholder='Choisir une promenade libre',options=[discord.SelectOption(label=data[0],value=code) for code,data in aventures.WALKS.items()])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id or interaction.guild is None:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        with engine.connect(DB) as con:
            if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',(self.pet_id,self.owner_id,interaction.guild.id)).fetchone():
                return await interaction.response.send_message('Compagnon introuvable.',ephemeral=True)
        session=aventures.start(self.values[0])
        with engine.connect(DB) as con:
            pet=engine.snapshot(con,self.pet_id,self.owner_id,interaction.guild.id)
        if pet is None:
            return await interaction.response.send_message('Compagnon introuvable.',ephemeral=True)
        stage,_=engine.stage(pet)
        mood,_=engine.mood(pet)
        try:
            picture = discord.File(nox_junior_visual.compose_walk(dict(pet),session['code'],stage=stage,mood=mood),filename='promenade.png')
        except (ValueError,OSError) as exc:
            return await interaction.response.send_message('Illustration de promenade indisponible.',ephemeral=True)
        await interaction.response.edit_message(content=None,embed=promenade_embed(session),attachments=[picture],view=PromenadeScene(self.pet_id,self.owner_id,session))


class PromenadeMenu(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.add_item(PromenadeSelect(pet_id,owner_id))


class InventoryView(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.pet_id,self.owner_id=pet_id,owner_id

    @discord.ui.button(label='Fabriquer une veilleuse',emoji='💡',row=0)
    async def craft_light(self,interaction,button):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: engine.craft(con,self.pet_id,self.owner_id,interaction.guild.id,'veilleuse')
            await interaction.response.send_message('💡 Veilleuse fabriquée !',ephemeral=True)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)

    @discord.ui.button(label='Fabriquer un coussin',emoji='🛏️',row=0)
    async def craft_cushion(self,interaction,button):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: engine.craft(con,self.pet_id,self.owner_id,interaction.guild.id,'coussin_etoile')
            await interaction.response.send_message('🛏️ Coussin fabriqué !',ephemeral=True)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)

    @discord.ui.button(label='Offrir un objet',emoji='🎁',row=1)
    async def gift(self,interaction,button):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        await interaction.response.send_message('Choisis le membre destinataire (il doit déjà posséder un NOX Junior).',view=GiftRecipientView(self.pet_id,self.owner_id),ephemeral=True)


class GiftRecipientSelect(discord.ui.UserSelect):
    def __init__(self,pet_id,owner_id):
        super().__init__(placeholder='Destinataire du cadeau',min_values=1,max_values=1)
        self.pet_id,self.owner_id=pet_id,owner_id

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        target=self.values[0]
        with engine.connect(DB) as con:
            receivers=engine.pets(con,interaction.guild.id,target.id)
            available=[r for r in engine.inventory(con,self.pet_id,self.owner_id,interaction.guild.id) if r['giftable']]
        if not receivers or not available: return await interaction.response.send_message('Aucun compagnon destinataire ou objet transférable disponible.',ephemeral=True)
        await interaction.response.send_message('Choisis l’objet à offrir (1 unité). Le destinataire devra confirmer.',view=GiftItemView(self.pet_id,self.owner_id,receivers[0]['id'],available),ephemeral=True)


class GiftRecipientView(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.add_item(GiftRecipientSelect(pet_id,owner_id))


class GiftItemSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id,recipient_pet,items):
        self.pet_id,self.owner_id,self.recipient_pet=pet_id,owner_id,recipient_pet
        super().__init__(placeholder='Objet à offrir',options=[discord.SelectOption(label=r['label'][:100],value=r['code']) for r in items[:25]])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: gift_id=engine.gift_offer(con,self.pet_id,self.owner_id,interaction.guild.id,self.recipient_pet,self.values[0])
            await interaction.response.send_message(f'🎁 Proposition de cadeau n°{gift_id} enregistrée. Le destinataire peut la consulter dans /monnox → Cadeaux.',ephemeral=True)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)


class GiftItemView(discord.ui.View):
    def __init__(self,pet_id,owner_id,recipient_pet,items):
        super().__init__(timeout=180)
        self.add_item(GiftItemSelect(pet_id,owner_id,recipient_pet,items))


class GiftDecision(discord.ui.View):
    def __init__(self,gift_id,owner_id):
        super().__init__(timeout=180)
        self.gift_id,self.owner_id=gift_id,owner_id

    async def resolve(self,interaction,accept):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: status=engine.gift_resolve(con,self.gift_id,self.owner_id,interaction.guild.id,accept)
            await interaction.response.edit_message(content=f'🎁 Cadeau : {status}.',view=None)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)

    @discord.ui.button(label='Accepter',style=discord.ButtonStyle.success)
    async def yes(self,interaction,button): await self.resolve(interaction,True)

    @discord.ui.button(label='Refuser',style=discord.ButtonStyle.danger)
    async def no(self,interaction,button): await self.resolve(interaction,False)


class GiftInboxSelect(discord.ui.Select):
    def __init__(self,owner_id,gifts):
        self.owner_id=owner_id
        super().__init__(placeholder='Choisir une proposition',options=[discord.SelectOption(label=f"Cadeau #{g['id']} : {g['code']} ×{g['quantity']}",value=str(g['id'])) for g in gifts[:20]])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        gift_id=int(self.values[0]);await interaction.response.send_message(f'Accepter le cadeau n°{gift_id} ?',view=GiftDecision(gift_id,self.owner_id),ephemeral=True)


class GiftInboxView(discord.ui.View):
    def __init__(self,owner_id,gifts):
        super().__init__(timeout=180);self.add_item(GiftInboxSelect(owner_id,gifts))


class RoomThemeSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id):
        self.pet_id,self.owner_id=pet_id,owner_id
        super().__init__(placeholder='Ambiance de la chambre',options=[discord.SelectOption(label=engine.ROOM_LABELS[i],value=x) for i,x in enumerate(engine.ROOM_THEMES)])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: engine.decorate(con,self.pet_id,self.owner_id,interaction.guild.id,theme=self.values[0])
            await interaction.response.send_message('🏠 Chambre choisie ! Ton Oreiller douillet exclusif est offert lors du premier choix !',ephemeral=True)
        except engine.JuniorError as exc:
            await interaction.response.send_message(str(exc),ephemeral=True)


class RoomDecorationSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id,decorations):
        self.pet_id,self.owner_id=pet_id,owner_id
        options=[discord.SelectOption(label='Retirer toutes les décorations',value='none')]+[discord.SelectOption(label=r['label'],value=r['code']) for r in decorations if r['code'] in engine.DECOR_SLOTS][:24]
        super().__init__(placeholder='Décoration à installer',options=options)

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con: engine.decorate(con,self.pet_id,self.owner_id,interaction.guild.id,decoration=self.values[0])
            await interaction.response.send_message('✨ Décoration installée !',ephemeral=True)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)


class ShopSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id):
        self.pet_id,self.owner_id=pet_id,owner_id
        super().__init__(placeholder='Acheter une décoration avec des poussières',options=[discord.SelectOption(label=f'{name} — {price} poussières',value=code) for code,(name,price,slot) in engine.SHOP.items()])

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id: return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                price=engine.purchase_decoration(con,self.pet_id,self.owner_id,interaction.guild.id,self.values[0])
                balance=engine.wallet(con,self.pet_id,self.owner_id,interaction.guild.id)['balance']
            await interaction.response.send_message(f'✨ Décoration achetée et installée ! -{price} poussières. Solde : {balance}.',ephemeral=True)
        except engine.JuniorError as exc: await interaction.response.send_message(str(exc),ephemeral=True)


class ShopView(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.add_item(ShopSelect(pet_id,owner_id))


class RoomView(discord.ui.View):
    def __init__(self,pet_id,owner_id,decorations):
        super().__init__(timeout=180)
        self.pet_id = pet_id
        self.owner_id = owner_id
        self.add_item(RoomThemeSelect(pet_id,owner_id))
        self.add_item(RoomDecorationSelect(pet_id,owner_id,decorations))

    @discord.ui.button(label='Boutique',emoji='✨',style=discord.ButtonStyle.primary)
    async def shop(self,interaction,button):
        with engine.connect(DB) as con:
            account=engine.wallet(con,self.pet_id,interaction.user.id,interaction.guild.id)
        await interaction.response.send_message(f'✨ **Boutique NOX Junior** — Solde : **{account["balance"]} poussières**\n10 et 20 soins réussis par jour = +1 poussière chacun (40 soins maximum) ; mini-jeu terminé = +2 (5 parties récompensées par jour).\nL’Oreiller douillet est un cadeau exclusif, non vendu.',view=ShopView(self.pet_id,interaction.user.id),ephemeral=True)


class CompliciteScene(discord.ui.View):
    """Private multi-step activity; no reward, care counter or rest restriction."""
    def __init__(self, pet_id, owner_id, pet_name, session):
        super().__init__(timeout=300)
        self.pet_id, self.owner_id, self.pet_name, self.session = pet_id, owner_id, pet_name, session
        if not session['done']:
            for index, label in enumerate(complicite.choices(session)):
                button = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary, row=index // 5)
                async def choose(interaction, index=index):
                    if interaction.user.id != self.owner_id:
                        return await interaction.response.send_message('Cette activité ne t’appartient pas.', ephemeral=True)
                    try:
                        with engine.connect(DB) as con:
                            engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
                            result = complicite.advance(self.session, index)
                            if result['done']:
                                personnalite.record(con, self.pet_id, 'complicite:'+result['activity'])
                                reaction = personnalite.reaction(personnalite.profile(con,self.pet_id), result['activity'])
                    except (engine.JuniorError, ValueError) as exc:
                        return await interaction.response.send_message(str(exc), ephemeral=True)
                    await interaction.response.edit_message(
                        content=f"{complicite.ACTIVITIES[result['activity']]['title']} · **{discord.utils.escape_markdown(self.pet_name)}**\n\n{result['text']}"
                                + ('\n\n💜 Un joli moment partagé. Tu peux recommencer quand tu veux.\n'+reaction if result['done'] else '\n\nQue fais-tu ensuite ?'),
                        view=CompliciteScene(self.pet_id, self.owner_id, self.pet_name, result))
                button.callback = choose
                self.add_item(button)
        again = discord.ui.Button(label='Autres activités', emoji='💜', style=discord.ButtonStyle.primary, row=3)
        async def back(interaction):
            if interaction.user.id != self.owner_id:
                return await interaction.response.send_message('Cette activité ne t’appartient pas.', ephemeral=True)
            await interaction.response.edit_message(content='💜 Choisis un moment à partager avec NOX :', view=CompliciteMenu(self.pet_id, self.owner_id))
        again.callback = back
        self.add_item(again)


class CompliciteMenu(discord.ui.View):
    def __init__(self, pet_id, owner_id):
        super().__init__(timeout=300)
        self.pet_id, self.owner_id = pet_id, owner_id
        for activity, label, emoji in [('parler', 'Discuter', '💬'), ('histoires', 'Histoires', '📖'),
                                       ('jouets', 'Jouets', '🧸'), ('calme', 'Moments calmes', '🌙')]:
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
            async def launch(interaction, activity=activity):
                if interaction.user.id != self.owner_id:
                    return await interaction.response.send_message('Cette activité ne t’appartient pas.', ephemeral=True)
                try:
                    with engine.connect(DB) as con:
                        pet = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
                except engine.JuniorError as exc:
                    return await interaction.response.send_message(str(exc), ephemeral=True)
                session = complicite.start(activity)
                await interaction.response.edit_message(
                    content=f"{complicite.ACTIVITIES[activity]['title']} · **{discord.utils.escape_markdown(pet['name'])}**\n\n{session['text']}",
                    view=CompliciteScene(self.pet_id, self.owner_id, pet['name'], session))
            button.callback = launch
            self.add_item(button)


class PetAdvancedView(discord.ui.View):
    def __init__(self, pet_id):
        super().__init__(timeout=180)
        self.pet_id = pet_id
        self._visual_seq = 0

    async def interaction_check(self, interaction):
        with engine.connect(DB) as con:
            row = con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?', (self.pet_id, interaction.user.id, interaction.guild.id if interaction.guild else 0)).fetchone()
        if row is None:
            await interaction.response.send_message('Ce NOX ne t’appartient pas.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Nourrir', emoji='🍎', style=discord.ButtonStyle.secondary, row=0)
    async def feed(self, interaction, button):
        await self._care(interaction, 'nourrir')

    @discord.ui.button(label='Boire', emoji='💧', style=discord.ButtonStyle.secondary, row=0)
    async def drink(self, interaction, button):
        await self._care(interaction, 'boire')

    @discord.ui.button(label='Jouer', emoji='🎮', style=discord.ButtonStyle.secondary, row=0)
    async def play(self, interaction, button):
        await self._care(interaction, 'jouer')

    @discord.ui.button(label='Câlin', emoji='💜', style=discord.ButtonStyle.secondary, row=0)
    async def hug(self, interaction, button):
        await self._care(interaction, 'calin')

    @discord.ui.button(label='Laver', emoji='🫧', style=discord.ButtonStyle.secondary, row=0)
    async def wash(self, interaction, button):
        await self._care(interaction, 'laver')

    @discord.ui.button(label='Repos', emoji='💤', style=discord.ButtonStyle.secondary, row=1)
    async def rest(self, interaction, button):
        await self._care(interaction, 'repos')

    @discord.ui.button(label='Actualiser', emoji='🔄', style=discord.ButtonStyle.primary, row=1)
    async def refresh(self, interaction, button):
        self._visual_seq += 1
        with engine.connect(DB) as con:
            row = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
        with engine.connect(DB) as con:
            purse=engine.wallet(con,self.pet_id,interaction.user.id,interaction.guild.id)
            picture=room_picture(con,self.pet_id,interaction.user.id,interaction.guild.id,row)
        await interaction.response.edit_message(embed=visual_embed(row,purse),attachments=[picture],view=self)

    @discord.ui.button(label='Mon bilan', emoji='📊', style=discord.ButtonStyle.secondary, row=1)
    async def dashboard(self, interaction, button):
        with engine.connect(DB) as con:
            pet = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
            purse = engine.wallet(con, self.pet_id, interaction.user.id, interaction.guild.id)
            room_info = engine.room(con, self.pet_id, interaction.user.id, interaction.guild.id)
        current_stage, days = engine.stage(pet)
        stage_names = {'oeuf':'Œuf', 'nouveau_ne':'Nouveau-né', 'bebe':'Bébé',
                       'adolescent':'Adolescent', 'adulte':'Adulte'}
        next_stage = {'oeuf':1, 'nouveau_ne':7, 'bebe':19, 'adolescent':40}
        gauge_names = {'satiete':'Faim', 'hydratation':'Hydratation',
                       'bonheur':'Bonheur', 'energie':'Énergie', 'hygiene':'Hygiène'}
        bars = []
        for key, label in gauge_names.items():
            value = max(0, min(100, int(pet[key])))
            bars.append(f'{label} : {"▰" * (value // 10)}{"▱" * (10 - value // 10)} **{value}%**')
        remaining = next_stage.get(current_stage)
        evolution = (f'Prochain seuil d’âge : J{remaining} (dans {max(0,remaining-days)} jour(s)), '
                     'sous réserve des conditions de soins et d’activités.' if remaining is not None
                     else 'Stade adulte atteint.')
        embed = discord.Embed(title='📊 Bilan de NOX Junior', color=0x7864CC)
        embed.add_field(name='🌱 Croissance', value=f'**{stage_names.get(current_stage,current_stage)}** · Jour {days}\n{evolution}', inline=False)
        embed.add_field(name='💜 Besoins', value='\n'.join(bars), inline=False)
        embed.add_field(name='✨ Poussières d’étoiles',
                        value=f'**{purse["balance"]}** disponibles · **{purse["care_today"]}/40** soins aujourd’hui · **{min(purse["care_today"],20)}/20** soins récompensables', inline=False)
        embed.add_field(name='🏠 Chambre',
                        value=f'{room_info["theme"] or "À choisir après éclosion"} · {len(room_info["slots"])} décoration(s) installée(s)', inline=False)
        embed.set_footer(text='Les objets équipés peuvent modifier progressivement certaines jauges.')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='Journal', emoji='📖', style=discord.ButtonStyle.primary, row=1)
    async def journal(self, interaction, button):
        labels = {'adoption':'🥚 Adoption', 'renommage':'✏️ Nouveau prénom', 'soin:nourrir':'🍎 Repas',
                  'soin:boire':'💧 Boisson', 'soin:jouer':'🎮 Jeu', 'soin:calin':'💜 Câlin',
                  'soin:laver':'🫧 Bain', 'soin:repos':'💤 Repos'}
        with engine.connect(DB) as con:
            events = engine.journal(con, self.pet_id, interaction.user.id, interaction.guild.id, limit=6)
            notes = engine.note_list(con,self.pet_id,interaction.user.id,interaction.guild.id,limit=20)
        lines = [f"• {labels.get(e['event'], e['event'])} · <t:{int(e['created_at'])}:R>" for e in events]
        embed = discord.Embed(title='📖 Journal de mon NOX',
            description='**Souvenirs automatiques**\n'+('\n'.join(lines) if lines else 'Aucun pour le moment.')+
                f'\n\n**Mes notes privées : {len(notes)} affichée(s)**\nSélectionne une note pour la lire, la modifier, la supprimer ou la partager.',
            color=0x7864CC)
        await interaction.response.send_message(embed=embed,
            view=JournalView(self.pet_id,interaction.user.id,notes),ephemeral=True)

    @discord.ui.button(label='Renommer', emoji='✏️', style=discord.ButtonStyle.secondary, row=1)
    async def rename(self, interaction, button):
        await interaction.response.send_modal(RenameModal(self.pet_id))

    @discord.ui.button(label='Mini-jeux',emoji='⭐',style=discord.ButtonStyle.primary,row=2)
    async def games(self,interaction,button):
        await interaction.response.send_message('🎮 Choisis une activité parmi les douze mini-jeux. Tu peux rejouer autant que tu veux ! Les cinq premières parties terminées chaque jour rapportent 2 poussières chacune.',view=GamesMenu(self.pet_id,interaction.user.id),ephemeral=True)

    @discord.ui.button(label='Explorer',emoji='🧭',style=discord.ButtonStyle.primary,row=2)
    async def explore(self,interaction,button):
        await interaction.response.send_message('🧭 **Explorations** : expéditions avec découvertes et délai.\n🚶 **Promenades** : aventures libres, sans délai ni poussières.',view=ExplorationMenu(self.pet_id,interaction.user.id),ephemeral=True)

    @discord.ui.button(label='Complicité', emoji='💜', style=discord.ButtonStyle.primary, row=2)
    async def complicity(self, interaction, button):
        await interaction.response.send_message(
            '💜 **La vie avec NOX** — Discussions, histoires, jouets et moments calmes. '
            'Activités rejouables, sans poussières et accessibles même pendant les pauses.',
            view=CompliciteMenu(self.pet_id, interaction.user.id), ephemeral=True)

    @discord.ui.button(label='Portrait',emoji='🎨',style=discord.ButtonStyle.secondary,row=2)
    async def portrait(self,interaction,button):
        with engine.connect(DB) as con:
            pet=engine.snapshot(con,self.pet_id,interaction.user.id,interaction.guild.id)
            info=engine.room(con,self.pet_id,interaction.user.id,interaction.guild.id)
        await interaction.response.send_message(file=discord.File(baby_portrait(pet,info),filename='portrait_nox.png'),ephemeral=True)

    @discord.ui.button(label='Découvertes',emoji='📚',style=discord.ButtonStyle.secondary,row=3)
    async def discoveries(self,interaction,button):
        with engine.connect(DB) as con:
            found=engine.discoveries(con,self.pet_id,interaction.user.id,interaction.guild.id)
        lines=[f'• **{engine.REGIONS[r["region"]][0]}** : {discord.utils.escape_markdown(r["discovery"])}' for r in found[:15]]
        with engine.connect(DB) as con:
            memories=engine.walk_memories(con,self.pet_id,interaction.user.id,interaction.guild.id)
        album=[f'• **{aventures.WALKS[r["region"]][0]}** : {discord.utils.escape_markdown(r["souvenir"])} · ×{r["visits"]}' for r in memories if r['region'] in aventures.WALKS]
        await interaction.response.send_message('📚 **Carnet des découvertes**\n'+('\n'.join(lines) if lines else 'Aucune découverte pour le moment.')+'\n\n📸 **Album des promenades**\n'+('\n'.join(album) if album else 'Aucun souvenir pour le moment.'),ephemeral=True)

    @discord.ui.button(label='Talents',emoji='✨',style=discord.ButtonStyle.secondary,row=3)
    async def talents(self,interaction,button):
        with engine.connect(DB) as con:
            points=engine.affinities(con,self.pet_id,interaction.user.id,interaction.guild.id)
            row=engine.snapshot(con,self.pet_id,interaction.user.id,interaction.guild.id)
        level,days=engine.stage(row)
        strongest=max(points,key=points.get)
        if level in ('adolescent','adulte') and points[strongest]>=15:
            msg=f'🌟 Talent dominant : **{engine.AFFINITY_LABELS[strongest]}** !'
        else:
            msg='🌱 Ton compagnon découvre encore sa personnalité.'
        msg+='\n'+ '\n'.join(f'• {label} : {points[key]}' for key,label in engine.AFFINITY_LABELS.items())
        await interaction.response.send_message(msg,ephemeral=True)

    @discord.ui.button(label='Personnalité', emoji='🐉', style=discord.ButtonStyle.secondary, row=3)
    async def personality(self, interaction, button):
        with engine.connect(DB) as con:
            pet = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
            values = personnalite.profile(con, self.pet_id)
        lines = [f'{personnalite.LABELS[t]} : **{values[t]}/100**' for t in personnalite.TRAITS]
        await interaction.response.send_message(
            f'🐉 **Personnalité de {discord.utils.escape_markdown(pet["name"])}**\n'
            + '\n'.join(lines) + '\n\n' + personnalite.description(values)
            + '\n\n💜 La personnalité évolue avec vos activités terminées. '
              'Chaque activité contribue au maximum une fois par jour ; tu peux toujours rejouer librement.',
            ephemeral=True)

    @discord.ui.button(label='Sac cosmique',emoji='🎒',style=discord.ButtonStyle.primary,row=3)
    async def bag(self,interaction,button):
        with engine.connect(DB) as con: items=engine.inventory(con,self.pet_id,interaction.user.id,interaction.guild.id)
        lines=[f"• **{discord.utils.escape_markdown(r['label'])}** ×{r['quantity']} ({r['category']})" for r in items]
        await interaction.response.send_message('🎒 **Inventaire personnel**\n'+('\n'.join(lines[:35]) if lines else 'Ton sac est vide. Les récompenses arriveront avec les aventures et activités.'),view=InventoryView(self.pet_id,interaction.user.id),ephemeral=True)

    @discord.ui.button(label='Chambre',emoji='🏠',style=discord.ButtonStyle.secondary,row=4)
    async def room(self,interaction,button):
        with engine.connect(DB) as con:
            info=engine.room(con,self.pet_id,interaction.user.id,interaction.guild.id)
            decos=[r for r in engine.inventory(con,self.pet_id,interaction.user.id,interaction.guild.id) if r['category']=='decoration']
        with engine.connect(DB) as con:
            pet=engine.snapshot(con,self.pet_id,interaction.user.id,interaction.guild.id)
        picture=discord.File(baby_portrait(pet,info),filename='chambre_nox.png')
        embed=discord.Embed(title='🏠 Chambre personnelle',description=f"Ambiance : **{info['theme'] or 'À choisir après éclosion'}**\nDécorations installées : **{len(info['slots'])}**",color=0x7864CC)
        embed.set_image(url='attachment://chambre_nox.png')
        await interaction.response.send_message(embed=embed,file=picture,view=RoomView(self.pet_id,interaction.user.id,decos),ephemeral=True)

    @discord.ui.button(label='Cadeaux reçus',emoji='🎁',style=discord.ButtonStyle.secondary,row=4)
    async def gifts(self,interaction,button):
        with engine.connect(DB) as con: gifts=engine.gifts_received(con,interaction.user.id,interaction.guild.id)
        if not gifts: return await interaction.response.send_message('🎁 Aucun cadeau en attente.',ephemeral=True)
        await interaction.response.send_message(f'🎁 Tu as {len(gifts)} proposition(s) en attente. Elles expirent après 24 heures.',view=GiftInboxView(interaction.user.id,gifts),ephemeral=True)

    @discord.ui.button(label='Rencontres',emoji='🤝',style=discord.ButtonStyle.primary,row=4)
    async def social(self,interaction,button):
        with engine.connect(DB) as con:
            encounters=engine.encounter_inbox(con,interaction.user.id,interaction.guild.id)
        # The inbox may contain invitations for either of a member's two companions.
        view=discord.ui.View(timeout=180)
        if encounters: view.add_item(SocialEncounterSelect(self.pet_id,interaction.user.id,encounters))
        invite=discord.ui.Button(label='Inviter un compagnon',emoji='💌',style=discord.ButtonStyle.success)
        async def invite_callback(i):
            if i.user.id!=interaction.user.id:
                return await i.response.send_message('Accès refusé.',ephemeral=True)
            await i.response.send_message('Choisis un jeu coopératif :',view=SocialGameView(self.pet_id,interaction.user.id),ephemeral=True)
        invite.callback=invite_callback
        view.add_item(invite)
        await interaction.response.send_message('🤝 **Rencontres cosmiques** · Invitations consenties, jeux à deux et souvenirs communs. Consulte tes invitations ou invite un ami.',view=view,ephemeral=True)

    async def _care(self, interaction, action):
        try:
            with engine.connect(DB) as con:
                engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
                remaining = engine.care(con, self.pet_id, interaction.user.id, action, guild_id=interaction.guild.id)
                row = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
        except engine.JuniorError as exc:
            # A daily cap or an unavailable companion must never leave a Discord
            # button spinning with the generic "Interaction failed" message.
            return await interaction.response.send_message(str(exc), ephemeral=True)
        if remaining:
            return await interaction.response.send_message(
                f'💤 NOX fait une petite pause : encore {remaining // 60 + 1} minute(s) au maximum. '
                'Tu peux toujours consulter sa chambre, son journal et ses décorations.',ephemeral=True)
        reactions={'nourrir':('heureux','🍎 Miam ! NOX se régale !'),
                   'boire':('heureux','💧 NOX se désaltère !'),
                   'jouer':('heureux','🎮 NOX s’amuse beaucoup !'),
                   'calin':('heureux','💜 NOX adore ce câlin !'),
                   'laver':('heureux','🫧 NOX est tout propre !'),
                   'repos':('endormi','💤 NOX ferme les yeux et se détend…')}
        self._visual_seq += 1
        visual_seq = self._visual_seq
        emotion, message = reactions[action]
        with engine.connect(DB) as con:
            purse=engine.wallet(con,self.pet_id,interaction.user.id,interaction.guild.id)
            picture=room_picture(con,self.pet_id,interaction.user.id,interaction.guild.id,row,emotion)
        await interaction.response.edit_message(embed=visual_embed(row,purse,message),attachments=[picture],view=self)
        async def restore():
            import asyncio
            await asyncio.sleep(7)
            if visual_seq != self._visual_seq: return
            try:
                with engine.connect(DB) as con:
                    fresh=engine.snapshot(con,self.pet_id,interaction.user.id,interaction.guild.id)
                    current_purse=engine.wallet(con,self.pet_id,interaction.user.id,interaction.guild.id)
                    image=room_picture(con,self.pet_id,interaction.user.id,interaction.guild.id,fresh)
                await interaction.edit_original_response(embed=visual_embed(fresh,current_purse),attachments=[image],view=self)
            except (discord.HTTPException, engine.JuniorError):
                pass
        import asyncio
        asyncio.create_task(restore())



# V2.0: small, discoverable navigation; existing handlers stay intact.
JUNIOR_MENUS = {
    'loisirs': ('🎮 S’amuser', 'Jeux, jouets et moments à partager.', [
        ('Mini-jeux', '⭐', 'games'), ('Complicité', '💜', 'complicity'),
        ('Explorer', '🧭', 'explore')]),
    'maison': ('🏠 Mon univers', 'Chambre, décoration et affaires.', [
        ('Ma chambre', '🏠', 'room'), ('Sac cosmique', '🎒', 'bag'),
        ('Cadeaux reçus', '🎁', 'gifts'), ('Portrait', '🎨', 'portrait')]),
    'souvenirs': ('📖 Mon compagnon', 'Suivre son évolution et ses souvenirs.', [
        ('Mon bilan', '📊', 'dashboard'), ('Journal', '📖', 'journal'),
        ('Découvertes', '📚', 'discoveries'), ('Personnalité', '🐉', 'personality'),
        ('Talents', '✨', 'talents')]),
    'ensemble': ('🤝 Rencontres et réglages', 'Rencontrer d’autres NOX et personnaliser le sien.', [
        ('Rencontres', '🤝', 'social'), ('Renommer', '✏️', 'rename'), ('Adopter un autre NOX', '🥚', 'adopt_another')]),
}


class JuniorCategoryView(discord.ui.View):
    def __init__(self, pet_id, owner_id, category):
        super().__init__(timeout=300)
        self.pet_id, self.owner_id, self.category = pet_id, owner_id, category
        for label, emoji, method in JUNIOR_MENUS[category][2]:
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
            async def open_feature(interaction, method=method):
                if interaction.user.id != self.owner_id:
                    return await interaction.response.send_message('Ce panneau ne t’appartient pas.', ephemeral=True)
                # Reuse the original, tested feature handlers rather than duplicating logic.
                if method == 'adopt_another':
                    with engine.connect(DB) as con:
                        rows = engine.pets(con, interaction.guild.id, interaction.user.id)
                        grant = con.execute('SELECT 1 FROM junior_grants WHERE guild_id=? AND owner_id=?', (interaction.guild.id, interaction.user.id)).fetchone()
                    if len(rows) >= (2 if grant else 1):
                        return await interaction.response.send_message('Tu as déjà atteint ton nombre maximum de compagnons.', ephemeral=True)
                    return await interaction.response.send_message('Choisis la couleur de ton nouvel œuf :', view=AdoptionView(), ephemeral=True)
                legacy = PetAdvancedView(self.pet_id)
                await getattr(legacy, method).callback(interaction)
            button.callback = open_feature
            self.add_item(button)
        back = discord.ui.Button(label='Retour à mon NOX', emoji='🐉', style=discord.ButtonStyle.primary, row=2)
        async def go_home(interaction):
            if interaction.user.id != self.owner_id:
                return await interaction.response.send_message('Ce panneau ne t’appartient pas.', ephemeral=True)
            with engine.connect(DB) as con:
                pet = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
                purse = engine.wallet(con, self.pet_id, interaction.user.id, interaction.guild.id)
                picture = room_picture(con, self.pet_id, interaction.user.id, interaction.guild.id, pet)
            await interaction.response.edit_message(content=None, embed=visual_embed(pet,purse), attachments=[picture], view=PetView(self.pet_id))
        back.callback = go_home
        self.add_item(back)


class PetView(PetAdvancedView):
    """V2.0 home: six immediate actions plus four clear navigation groups."""
    def __init__(self, pet_id):
        super().__init__(pet_id)
        self.clear_items()
        for index, (label, emoji, action) in enumerate([
            ('Nourrir','🍎','nourrir'), ('Boire','💧','boire'),
            ('Jouer','🎮','jouer'), ('Câlin','💜','calin'),
            ('Laver','🫧','laver'), ('Repos','💤','repos')]):
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=index // 5)
            async def care(interaction, action=action):
                await self._care(interaction, action)
            button.callback = care
            self.add_item(button)
        for index, (category, label, emoji) in enumerate([
            ('loisirs','S’amuser','⭐'), ('maison','Mon univers','🏠'),
            ('souvenirs','Mon compagnon','📖'), ('ensemble','Rencontres','🤝')]):
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary, row=2)
            async def show_category(interaction, category=category):
                title, description, _ = JUNIOR_MENUS[category]
                await interaction.response.send_message(
                    f'**{title}**\n{description}\n\nChoisis une activité ci-dessous.',
                    view=JuniorCategoryView(self.pet_id, interaction.user.id, category), ephemeral=True)
            button.callback = show_category
            self.add_item(button)
        refresh = discord.ui.Button(label='Actualiser les jauges', emoji='🔄', style=discord.ButtonStyle.secondary, row=3)
        async def update(interaction):
            self._visual_seq += 1
            with engine.connect(DB) as con:
                pet = engine.snapshot(con, self.pet_id, interaction.user.id, interaction.guild.id)
                purse = engine.wallet(con, self.pet_id, interaction.user.id, interaction.guild.id)
                picture = room_picture(con, self.pet_id, interaction.user.id, interaction.guild.id, pet)
            await interaction.response.edit_message(embed=visual_embed(pet,purse),attachments=[picture],view=self)
        refresh.callback = update
        self.add_item(refresh)



class SocialTarget(discord.ui.UserSelect):
    def __init__(self,pet_id,owner_id,game):
        super().__init__(placeholder='Choisir le membre à inviter',min_values=1,max_values=1)
        self.pet_id,self.owner_id,self.game=pet_id,owner_id,game

    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Cette invitation ne t’appartient pas.',ephemeral=True)
        target=self.values[0]
        if target.bot or target.id==self.owner_id:
            return await interaction.response.send_message('Choisis un autre membre humain.',ephemeral=True)
        with engine.connect(DB) as con:
            candidates=engine.pets(con,interaction.guild.id,target.id)
        if not candidates:
            return await interaction.response.send_message('Ce membre ne possède pas encore de NOX Junior.',ephemeral=True)
        if len(candidates)==1:
            return await self.send_invite(interaction,candidates[0]['id'])
        await interaction.response.send_message('Choisis le compagnon à inviter :',view=SocialPetSelectView(self.pet_id,self.owner_id,self.game,candidates),ephemeral=True)

    async def send_invite(self,interaction,target_pet):
        try:
            with engine.connect(DB) as con:
                invitation=engine.encounter_invite(con,self.pet_id,self.owner_id,interaction.guild.id,target_pet,self.game)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        await interaction.response.send_message(f'💌 Invitation #{invitation} envoyée ! Le membre pourra la consulter dans `/monnox` → Rencontres. Elle expire après 24 heures.',ephemeral=True)


class SocialPetSelect(discord.ui.Select):
    def __init__(self,source,owner,game,pets):
        super().__init__(placeholder='Quel compagnon ?',options=[discord.SelectOption(label=r['name'][:90],value=str(r['id'])) for r in pets])
        self.source,self.owner,self.game=source,owner,game
    async def callback(self,interaction):
        await SocialTarget(self.source,self.owner,self.game).send_invite(interaction,int(self.values[0])) if interaction.user.id==self.owner else await interaction.response.send_message('Accès refusé.',ephemeral=True)


class SocialPetSelectView(discord.ui.View):
    def __init__(self,source,owner,game,pets):
        super().__init__(timeout=180)
        self.add_item(SocialPetSelect(source,owner,game,pets))


class SocialTargetView(discord.ui.View):
    def __init__(self,pet_id,owner_id,game):
        super().__init__(timeout=180)
        self.add_item(SocialTarget(pet_id,owner_id,game))


class SocialGameSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id):
        super().__init__(placeholder='Choisir une activité à deux',options=[discord.SelectOption(label=info[0],value=key) for key,info in engine.SOCIAL_GAMES.items()])
        self.pet_id,self.owner_id=pet_id,owner_id
    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        await interaction.response.send_message('💌 Quel membre souhaites-tu inviter ?',view=SocialTargetView(self.pet_id,self.owner_id,self.values[0]),ephemeral=True)


class SocialGameView(discord.ui.View):
    def __init__(self,pet_id,owner_id):
        super().__init__(timeout=180)
        self.add_item(SocialGameSelect(pet_id,owner_id))


class SocialChoices(discord.ui.View):
    def __init__(self,encounter_id,pet_id,owner_id,game,progress):
        super().__init__(timeout=180)
        self.encounter_id,self.pet_id,self.owner_id=encounter_id,pet_id,owner_id
        for i,label in enumerate(progress['choices']):
            button=discord.ui.Button(label=label[:80],style=discord.ButtonStyle.secondary,row=i)
            async def act(interaction,choice=i):
                if interaction.user.id!=self.owner_id:
                    return await interaction.response.send_message('Accès refusé.',ephemeral=True)
                try:
                    with engine.connect(DB) as con:
                        result=engine.encounter_play(con,self.encounter_id,self.pet_id,self.owner_id,interaction.guild.id,choice)
                except engine.JuniorError as exc:
                    return await interaction.response.send_message(str(exc),ephemeral=True)
                self.stop()
                if result['completed']:
                    msg=f'🎉 Trois manches terminées ! Les deux NOX gagnent {result["reward"]} points de complicité.'
                elif result['round_complete']:
                    msg=f'✨ Manche {result["round"]}/3 terminée ! La manche suivante est disponible dans `/monnox` → Rencontres.'
                else:
                    msg=f'✨ Manche {result["round"]}/3 : choix enregistré. Ton partenaire doit jouer pour débloquer la suite.'
                await interaction.response.edit_message(content=msg,view=None)
            button.callback=act
            self.add_item(button)


class SocialEncounterSelect(discord.ui.Select):
    def __init__(self,pet_id,owner_id,encounters):
        options=[]
        for e in encounters:
            title=engine.SOCIAL_GAMES[e['game']][0]
            direction='Reçue' if e['invited_owner']==owner_id else 'Envoyée'
            options.append(discord.SelectOption(label=f'#{e["id"]} {title}'[:100],description=f'{direction} · {e["status"]}',value=str(e['id'])))
        super().__init__(placeholder='Sélectionner une rencontre',options=options[:25])
        self.pet_id,self.owner_id=pet_id,owner_id
    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        with engine.connect(DB) as con:
            matches=[e for e in engine.encounter_inbox(con,self.owner_id,interaction.guild.id) if e['id']==int(self.values[0])]
        if not matches:
            return await interaction.response.send_message('Cette rencontre est expirée ou terminée.',ephemeral=True)
        e=matches[0]
        if e['status']=='pending':
            if e['invited_owner']!=self.owner_id:
                return await interaction.response.send_message('💌 Invitation envoyée. En attente de la réponse du destinataire.',ephemeral=True)
            return await interaction.response.send_message('💌 Acceptes-tu cette rencontre ?',view=SocialConsent(e['id'],self.owner_id),ephemeral=True)
        pid=e['inviter_pet'] if e['inviter_owner']==self.owner_id else e['invited_pet']
        try:
            with engine.connect(DB) as con:
                progress=engine.encounter_progress(con,e['id'],pid,self.owner_id,interaction.guild.id)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        if progress['waiting']:
            return await interaction.response.send_message(f'⏳ Manche {progress["round"]}/3 : ton choix est enregistré. Attends ton partenaire.',ephemeral=True)
        await interaction.response.send_message(f'🌠 **{engine.SOCIAL_GAMES[e["game"]][0]}** · Manche {progress["round"]}/3\n{progress["prompt"]}',view=SocialChoices(e['id'],pid,self.owner_id,e['game'],progress),ephemeral=True)


class SocialInboxView(discord.ui.View):
    def __init__(self,pet_id,owner_id,encounters):
        super().__init__(timeout=180)
        self.add_item(SocialEncounterSelect(pet_id,owner_id,encounters))


class SocialConsent(discord.ui.View):
    def __init__(self,encounter_id,owner_id):
        super().__init__(timeout=180)
        self.encounter_id,self.owner_id=encounter_id,owner_id
    async def answer(self,interaction,accept):
        if interaction.user.id!=self.owner_id:
            return await interaction.response.send_message('Accès refusé.',ephemeral=True)
        try:
            with engine.connect(DB) as con:
                status=engine.encounter_respond(con,self.encounter_id,self.owner_id,interaction.guild.id,accept)
        except engine.JuniorError as exc:
            return await interaction.response.send_message(str(exc),ephemeral=True)
        await interaction.response.edit_message(content={'active':'💜 Rencontre acceptée ! Les deux membres peuvent jouer via `/monnox` → Rencontres.','declined':'Invitation refusée.','expired':'Invitation expirée.'}[status],view=None)
    @discord.ui.button(label='Accepter',style=discord.ButtonStyle.success)
    async def accept(self,interaction,button): await self.answer(interaction,True)
    @discord.ui.button(label='Refuser',style=discord.ButtonStyle.secondary)
    async def decline(self,interaction,button): await self.answer(interaction,False)

class GrantConfirm(discord.ui.View):
    def __init__(self, target_id, founder_id, guild_id):
        super().__init__(timeout=90)
        self.target_id,self.founder_id,self.guild_id=target_id,founder_id,guild_id

    @discord.ui.button(label='Confirmer le deuxième œuf',style=discord.ButtonStyle.success)
    async def confirm(self,interaction,button):
        if interaction.user.id != self.founder_id or not any(r.id==FOUNDER_ROLE for r in getattr(interaction.user,'roles',())):
            return await interaction.response.send_message('Réservé au Fondateur.',ephemeral=True)
        with engine.connect(DB) as con:
            engine.grant_second(con,self.guild_id,self.target_id,interaction.user.id)
        self.stop()
        await interaction.response.edit_message(content=f'🎁 Autorisation de deuxième adoption accordée à <@{self.target_id}>. Le membre pourra choisir son œuf avec `/monnox`.',view=None)

    @discord.ui.button(label='Annuler',style=discord.ButtonStyle.secondary)
    async def cancel(self,interaction,button):
        if interaction.user.id != self.founder_id:
            return await interaction.response.send_message('Réservé au Fondateur.',ephemeral=True)
        self.stop()
        await interaction.response.edit_message(content='Attribution annulée.',view=None)




# Persistent public invitations; one per guild/member even across bot restarts.
def init_invitation_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS junior_egg_invitations (
        guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
        message_id INTEGER, status TEXT NOT NULL DEFAULT 'pending',
        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
        PRIMARY KEY(guild_id, owner_id)
    )""")


class EggInvitationView(discord.ui.View):
    """Persistent buttons; only the mentioned member may use them."""
    def __init__(self, guild_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.owner_id = owner_id
        adopt = discord.ui.Button(label='J’accueille mon œuf !', emoji='🥚',
            style=discord.ButtonStyle.success,
            custom_id=f'noxjunior:egg:adopt:{guild_id}:{owner_id}')
        decline = discord.ui.Button(label='Pas encore, NOX !', emoji='🌙',
            style=discord.ButtonStyle.secondary,
            custom_id=f'noxjunior:egg:later:{guild_id}:{owner_id}')
        adopt.callback = self.accept
        decline.callback = self.later
        self.add_item(adopt)
        self.add_item(decline)

    async def _authorized(self, interaction):
        if interaction.guild_id != self.guild_id or interaction.user.id != self.owner_id:
            await interaction.response.send_message('💙 Ce cadeau cosmique est réservé à la personne mentionnée.', ephemeral=True)
            return False
        with engine.connect(DB) as con:
            init_invitation_table(con)
            row = con.execute('SELECT status FROM junior_egg_invitations WHERE guild_id=? AND owner_id=?',
                (self.guild_id, self.owner_id)).fetchone()
        if not row or row['status'] != 'pending':
            await interaction.response.send_message('🥚 Cette invitation est déjà clôturée. Utilise `/monnox` pour retrouver ton compagnon ou ton droit à l’adoption.', ephemeral=True)
            return False
        return True

    async def accept(self, interaction):
        if not await self._authorized(interaction):
            return
        with engine.connect(DB) as con:
            existing = engine.pets(con, self.guild_id, self.owner_id)
        if existing:
            await interaction.response.send_message('💜 Tu as déjà ton NOX Junior ! Retrouve-le avec `/monnox`.', ephemeral=True)
            return
        ok, count = eligible(interaction.user, self.guild_id)
        if not ok:
            await interaction.response.send_message(
                f'🥚 Ton œuf t’attend au chaud ! Il faut le rôle **Lien vivant** et **10 soins au NOX collectif** (actuellement {count}/10). Reviens ici quand tu seras prêt !',
                ephemeral=True)
            return
        await interaction.response.send_message('✨ NOX ouvre doucement son cadeau… Choisis la couleur de ton œuf !',
            view=AdoptionView(), ephemeral=True)

    async def later(self, interaction):
        if not await self._authorized(interaction):
            return
        with engine.connect(DB) as con:
            con.execute("UPDATE junior_egg_invitations SET status='declined' WHERE guild_id=? AND owner_id=? AND status='pending'",
                (self.guild_id, self.owner_id))
        await interaction.response.edit_message(view=None)
        await interaction.followup.send('🌙 Pas de souci ! NOX garde ton œuf au chaud. Tu pourras toujours l’adopter plus tard avec `/monnox`.', ephemeral=True)


def egg_invitation_embed(member):
    embed = discord.Embed(
        title='🌟 NOX a un cadeau cosmique pour toi !',
        description=(
            f'🎉 **Bravo {member.mention} !** Tu viens d’atteindre le rôle **Lien vivant** !\n\n'
            'En fouillant dans mes trésors galactiques, j’ai découvert un **œuf mystérieux** qui scintille rien que pour toi… 🥚✨\n\n'
            'Je le garde bien au chaud, mais il rêve peut-être déjà de rencontrer son meilleur ami.\n\n'
            '**Prêt à accueillir ton petit compagnon cosmique ?** 💙\n\n'
            '*Pour faire éclore ton premier œuf, il te faut aussi 10 soins au NOX collectif.*'
        ).replace('\\n', '\n'),
        color=0x247BFF,
    )
    embed.set_image(url='attachment://invitation_grand_nox.png')
    embed.set_footer(text='HORIZONS · Unis dans la diversité · Le cadeau du Grand NOX')
    return embed

class NoxJunior(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        with engine.connect(DB) as con:
            init_invitation_table(con)
            pending = con.execute("SELECT guild_id, owner_id FROM junior_egg_invitations WHERE status='pending' AND message_id IS NOT NULL").fetchall()
        for row in pending:
            bot.add_view(EggInvitationView(row['guild_id'], row['owner_id']))

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot or before.guild.id != after.guild.id:
            return
        old_roles = {role.id for role in before.roles}
        new_roles = {role.id for role in after.roles}
        if LIEN_VIVANT_ROLE not in new_roles or LIEN_VIVANT_ROLE in old_roles:
            return
        with engine.connect(DB) as con:
            init_invitation_table(con)
            if engine.pets(con, after.guild.id, after.id):
                return
            # Claim first, so duplicate events/restarts cannot publish twice.
            inserted = con.execute(
                "INSERT OR IGNORE INTO junior_egg_invitations(guild_id, owner_id) VALUES (?, ?)",
                (after.guild.id, after.id))
            if not inserted.rowcount:
                return
        channel = after.guild.get_channel(GIVEAWAY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(GIVEAWAY_CHANNEL_ID)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.exception('NOX Junior: salon giveaway inaccessible')
                return
        if getattr(channel, 'guild', None) and channel.guild.id != after.guild.id:
            log.error('NOX Junior: giveaway channel is not in the member guild')
            return
        view = EggInvitationView(after.guild.id, after.id)
        try:
            if INVITE_IMAGE.is_file():
                message = await channel.send(
                    content=after.mention,
                    embed=egg_invitation_embed(after),
                    file=discord.File(INVITE_IMAGE, filename='invitation_grand_nox.png'),
                    view=view,
                    allowed_mentions=discord.AllowedMentions(users=[after], roles=False, everyone=False),
                )
            else:
                embed = egg_invitation_embed(after)
                embed.set_image(url=None)
                message = await channel.send(content=after.mention, embed=embed, view=view,
                    allowed_mentions=discord.AllowedMentions(users=[after], roles=False, everyone=False))
        except (discord.Forbidden, discord.HTTPException):
            log.exception('NOX Junior: impossible de publier le cadeau pour %s', after.id)
            return
        with engine.connect(DB) as con:
            con.execute('UPDATE junior_egg_invitations SET message_id=? WHERE guild_id=? AND owner_id=?',
                (message.id, after.guild.id, after.id))

    @app_commands.command(name='monnox',description='Accueillir et retrouver ton compagnon NOX Junior')
    @app_commands.guild_only()
    async def monnox(self,interaction:discord.Interaction):
        with engine.connect(DB) as con:
            rows=engine.pets(con,interaction.guild.id,interaction.user.id)
            grant=con.execute('SELECT 1 FROM junior_grants WHERE guild_id=? AND owner_id=?',(interaction.guild.id,interaction.user.id)).fetchone()
        max_pets=2 if grant else 1
        ok,count=eligible(interaction.user,interaction.guild.id)
        can_adopt=len(rows)<max_pets and (ok or bool(grant and len(rows)==1))
        if not rows:
            if can_adopt:
                await interaction.response.send_message('🐣 Choisis la couleur de ton premier œuf !',view=AdoptionView(),ephemeral=True)
            else:
                await interaction.response.send_message(f'🐣 Adoption disponible avec le rôle **Lien vivant** et **10 soins** au NOX collectif. Tes soins : **{count}/10**.',ephemeral=True)
            return
        if len(rows)==1:
            with engine.connect(DB) as con:
                row=engine.snapshot(con,rows[0]['id'],interaction.user.id,interaction.guild.id)
                purse=engine.wallet(con,row['id'],interaction.user.id,interaction.guild.id)
                picture=room_picture(con,row['id'],interaction.user.id,interaction.guild.id,row)
            return await interaction.response.send_message(embed=visual_embed(row,purse),file=picture,view=PetView(row['id']),ephemeral=True)
        await interaction.response.send_message('💙 Voici tes compagnons :',view=PetListView(rows,can_adopt),ephemeral=True)

    @app_commands.command(name='montrermonnox',description='Présenter publiquement ton compagnon NOX Junior')
    @app_commands.guild_only()
    @app_commands.describe(compagnon='Numéro de ton compagnon (1 ou 2)')
    async def montrermonnox(self,interaction:discord.Interaction,compagnon:app_commands.Range[int,1,2]=1):
        with engine.connect(DB) as con:
            rows=engine.pets(con,interaction.guild.id,interaction.user.id)
            pet=next((r for r in rows if r['slot']==compagnon),None)
            if pet is None:
                return await interaction.response.send_message('🐣 Tu ne possèdes pas de NOX à cet emplacement. Utilise `/monnox` pour adopter.',ephemeral=True)
            row=engine.snapshot(con,pet['id'],interaction.user.id,interaction.guild.id)
            points=engine.affinities(con,pet['id'],interaction.user.id,interaction.guild.id)
            info=engine.room(con,pet['id'],interaction.user.id,interaction.guild.id)
        stage,days=engine.stage(row)
        mood,_=engine.mood(row)
        embed=discord.Embed(title=f'🐣 Voici {discord.utils.escape_markdown(row["name"])} !',description=f'Le compagnon cosmique de {interaction.user.mention} ✨\n\n**Âge :** {days} jour(s)\n**Stade :** {stage.replace("_"," ").capitalize()}\n**Couleur :** {row["color"].capitalize()}\n**Humeur :** {mood.capitalize()}\n**Complicité :** {row["bond"]} 💜\n**Aventures et activités :** {row["activities"]} ⭐',color=discord.Color.from_rgb(*PALETTE.get(row['color'],PALETTE['bleu'])))
        strongest=max(points,key=points.get)
        if stage in ('adolescent','adulte') and points[strongest]>=15:
            embed.add_field(name='🌟 Talent',value=engine.AFFINITY_LABELS[strongest],inline=False)
        embed.set_footer(text='HORIZONS · NOX Junior V0.8 · Présentation volontaire')
        embed.set_image(url='attachment://nox_junior.png')
        await interaction.response.send_message(embed=embed,file=discord.File(baby_portrait(row,info),filename='nox_junior.png'))

    @app_commands.command(name='givemonnox',description='Fondateur : autoriser un deuxième NOX Junior')
    @app_commands.guild_only()
    @app_commands.describe(membre='Membre bénéficiaire')
    async def givemonnox(self,interaction:discord.Interaction,membre:discord.Member):
        if not any(r.id==FOUNDER_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message('Commande réservée au Fondateur.',ephemeral=True)
        if membre.bot:
            return await interaction.response.send_message('Un bot ne peut pas adopter.',ephemeral=True)
        with engine.connect(DB) as con:
            rows=engine.pets(con,interaction.guild.id,membre.id)
            grant=con.execute('SELECT 1 FROM junior_grants WHERE guild_id=? AND owner_id=?',(interaction.guild.id,membre.id)).fetchone()
        if len(rows)>=2 or grant:
            return await interaction.response.send_message('Ce membre dispose déjà de son autorisation ou de deux compagnons.',ephemeral=True)
        await interaction.response.send_message(f'Offrir à {membre.mention} le droit à un **deuxième** NOX Junior ?',view=GrantConfirm(membre.id,interaction.user.id,interaction.guild.id),ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxJunior(bot))
