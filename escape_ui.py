"""Interface Discord des salles HORIZONS, réutilisable pour chaque aventure."""
from __future__ import annotations
import discord
import sqlite3
from pathlib import Path
from escape_engine import Engine, AdventureError


def player_is_authorized(database, key, user_id):
    """Check that the actor owns the solo session or belongs to its team.

    The engine's owner_id identifies a session, not the Discord actor.
    """
    guild_id, adventure, mode, owner_id = key
    if mode == 'solo':
        return user_id == owner_id
    if mode != 'team':
        return False
    with sqlite3.connect(database) as con:
        return con.execute(
            "SELECT 1 FROM teams t JOIN team_members m ON m.team_id=t.id "
            "WHERE t.id=? AND t.guild_id=? AND t.adventure=? AND m.user_id=?",
            (owner_id, guild_id, adventure, user_id),
        ).fetchone() is not None


async def reject_unauthorized(interaction, engine, key):
    if (interaction.guild_id == key[0] and
            player_is_authorized(engine.database, key, interaction.user.id)):
        return False
    await interaction.response.send_message(
        '⛔ Cette partie appartient à un autre joueur ou à une autre équipe.', ephemeral=True
    )
    return True


def room_for(content, state):
    return next((r for r in content['rooms'] if r['id'] == state['room_id']), None)


class AnswerModal(discord.ui.Modal, title='Répondre à une énigme'):
    response_text = discord.ui.TextInput(label='Ta réponse', max_length=200, required=True)

    def __init__(self, engine, content, guild_id, adventure, mode, owner_id, puzzle):
        super().__init__()
        self.engine, self.content = engine, content
        self.key = (guild_id, adventure, mode, owner_id)
        self.puzzle = puzzle

    async def on_submit(self, interaction: discord.Interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        try:
            result = self.engine.answer(*self.key, self.content, self.puzzle['id'], str(self.response_text))
        except AdventureError as exc:
            return await interaction.response.send_message(f'⚠️ {exc}', ephemeral=True)
        if result.get('already_solved'):
            msg = 'Cette énigme est déjà résolue.'
        elif result.get('reason') == 'missing_puzzles':
            msg = '🔒 D’autres épreuves doivent être résolues avant celle-ci.'
        elif result.get('reason') == 'missing_items':
            msg = '🔒 Il te manque un objet nécessaire.'
        elif not result['correct']:
            msg = '❌ Ce n’est pas la bonne réponse. Observe encore la salle.'
        elif result.get('finished'):
            msg = '🏆 Aventure terminée !'
        elif result.get('next_room'):
            msg = '🚪 La porte s’ouvre ! Une nouvelle salle est accessible.'
        else:
            msg = '✅ Épreuve réussie ! Une nouvelle découverte est enregistrée.'
        await interaction.response.send_message(msg, ephemeral=True)


class PuzzlePicker(discord.ui.Select):
    def __init__(self, engine, content, key, room, state):
        self.engine, self.content, self.key, self.room = engine, content, key, room
        options = []
        for p in room['puzzles'][:25]:
            solved = p['id'] in state['solved']
            options.append(discord.SelectOption(label=('✓ ' if solved else '') + p.get('title', 'Énigme')[:90], value=p['id'], description='Déjà résolue' if solved else 'Examiner cette épreuve'))
        super().__init__(placeholder='Choisir une énigme', options=options, row=0)

    async def callback(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        state = self.engine.status(*self.key)
        if not state or state['room_id'] != self.room['id']:
            return await interaction.response.send_message('Cette salle a changé. Rouvre ta progression.', ephemeral=True)
        puzzle = next(p for p in self.room['puzzles'] if p['id'] == self.values[0])
        access = self.engine.puzzle_access(*self.key, self.content, puzzle['id'])
        if not access['accessible']:
            return await interaction.response.send_message('🔒 Cette épreuve n’est pas encore accessible. Poursuis les découvertes précédentes.', ephemeral=True)
        description = puzzle.get('description', 'Observe attentivement la salle.')
        hints = len(puzzle.get('hints', []))
        await interaction.response.send_message(embed=discord.Embed(title=puzzle.get('title', 'Énigme'), description=description, color=0xc6993f), view=PuzzleActions(self.engine, self.content, self.key, puzzle), ephemeral=True)


class PuzzleActions(discord.ui.View):
    def __init__(self, engine, content, key, puzzle):
        super().__init__(timeout=900)
        self.engine, self.content, self.key, self.puzzle = engine, content, key, puzzle

    async def interaction_check(self, interaction):
        return not await reject_unauthorized(interaction, self.engine, self.key)

    @discord.ui.button(label='Répondre', style=discord.ButtonStyle.primary, emoji='🗝️')
    async def answer(self, interaction, button):
        await interaction.response.send_modal(AnswerModal(self.engine, self.content, *self.key, self.puzzle))

    @discord.ui.button(label='Indice', style=discord.ButtonStyle.secondary, emoji='💡')
    async def hint(self, interaction, button):
        try:
            result = self.engine.hint_for_current_puzzle(*self.key, self.content, self.puzzle['id'])
            if not result['accessible']:
                return await interaction.response.send_message('🔒 Cet indice sera disponible lorsque l’épreuve sera déverrouillée.', ephemeral=True)
            hint = result['hint']
        except AdventureError as exc:
            return await interaction.response.send_message(str(exc), ephemeral=True)
        await interaction.response.send_message('💡 ' + (hint or 'Aucun indice disponible pour cette épreuve.'), ephemeral=True)


class CombineModal(discord.ui.Modal, title='Assembler deux objets'):
    first = discord.ui.TextInput(label='Premier objet (nom dans l’inventaire)', max_length=100)
    second = discord.ui.TextInput(label='Deuxième objet (nom dans l’inventaire)', max_length=100)

    def __init__(self, engine, content, key):
        super().__init__()
        self.engine, self.content, self.key = engine, content, key

    async def on_submit(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        try:
            result = self.engine.combine(*self.key, self.content,
                                         str(self.first).strip(), str(self.second).strip())
        except AdventureError as exc:
            return await interaction.response.send_message(f'⚠️ {exc}', ephemeral=True)
        if result.get('combined'):
            message = '🧩 Assemblage déjà réalisé.' if result.get('already_created') else '🧩 Assemblage réussi ! Consulte ton inventaire.'
        elif result.get('reason') == 'missing_items':
            message = '🎒 Il manque un ou plusieurs objets dans ton inventaire.'
        else:
            message = '🔎 Ces objets ne semblent pas s’assembler ici.'
        await interaction.response.send_message(message, ephemeral=True)


class DecorPicker(discord.ui.Select):
    def __init__(self, engine, content, key, room):
        self.engine, self.content, self.key = engine, content, key
        options = [discord.SelectOption(label=h['title'][:100], value=h['id'])
                   for h in room.get('hotspots', [])[:25]]
        super().__init__(placeholder='🔎 Examiner un élément du décor', options=options, row=2)

    async def callback(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        try:
            result = self.engine.inspect(*self.key, self.content, self.values[0])
        except AdventureError as exc:
            return await interaction.response.send_message(f'⚠️ {exc}', ephemeral=True)
        if not result['accessible']:
            return await interaction.response.send_message('🔒 Cet élément ne peut pas encore être examiné.', ephemeral=True)
        message = result['description'] or 'Tu examines attentivement cet élément.'
        if result['new_items']:
            message += '\n🎒 Nouvelle découverte dans ton inventaire.'
        await interaction.response.send_message(message, ephemeral=True)


class RoomView(discord.ui.View):
    def __init__(self, engine, content, guild_id, adventure, mode, owner_id):
        super().__init__(timeout=900)
        self.engine, self.content = engine, content
        self.key = (guild_id, adventure, mode, owner_id)
        state = engine.status(*self.key)
        room = room_for(content, state) if state else None
        if room and room['puzzles']:
            self.add_item(PuzzlePicker(engine, content, self.key, room, state))
        if room and room.get('hotspots'):
            self.add_item(DecorPicker(engine, content, self.key, room))

    async def interaction_check(self, interaction):
        return not await reject_unauthorized(interaction, self.engine, self.key)

    @discord.ui.button(label='Inventaire', style=discord.ButtonStyle.secondary, emoji='🎒', row=1)
    async def inventory(self, interaction, button):
        state = self.engine.status(*self.key)
        items = state['items'] if state else []
        await interaction.response.send_message('🎒 **Inventaire :** ' + (', '.join(items) if items else 'vide'), ephemeral=True)

    @discord.ui.button(label='Assembler', style=discord.ButtonStyle.secondary, emoji='🧩', row=1)
    async def assemble(self, interaction, button):
        await interaction.response.send_modal(CombineModal(self.engine, self.content, self.key))

    @discord.ui.button(label='Actualiser la salle', style=discord.ButtonStyle.secondary, emoji='🔄', row=1)
    async def refresh(self, interaction, button):
        await show_room(interaction, self.engine, self.content, self.key)


async def show_room(interaction, engine, content, key):
    if await reject_unauthorized(interaction, engine, key):
        return
    state = engine.status(*key)
    if not state:
        return await interaction.response.send_message('Aucune partie active.', ephemeral=True)
    room = room_for(content, state)
    if not room:
        return await interaction.response.send_message('Salle introuvable.', ephemeral=True)
    solved = sum(p['id'] in state['solved'] for p in room['puzzles'])
    scene = engine.scene(*key, content)
    embed = discord.Embed(title=room['title'], description=scene['description'] + '\n\n**🔎 Cliquer sur l’image pour l’agrandir.**', color=0xc6993f)
    if scene['id'] != 'initial':
        embed.set_footer(text='✦ Le décor a évolué depuis votre arrivée.')
    embed.add_field(name='Épreuves résolues', value=f'{solved}/{len(room["puzzles"])}')
    events = engine.narrative_events(*key, content)
    if events['nox']:
        embed.add_field(name='🐾 NOX', value=events['nox'][:1024], inline=False)
    if events['echoes']:
        embed.add_field(name='✦ Échos retrouvés', value='\n'.join(e['text'] for e in events['echoes'])[:1024], inline=False)
    file = None
    if scene.get('image_file'):
        base = Path(__file__).resolve().parent / 'escape_content' / 'images'
        image_path = (base / scene['image_file']).resolve()
        if image_path.parent == base.resolve() and image_path.is_file():
            file = discord.File(image_path, filename=image_path.name)
            embed.set_image(url=f'attachment://{image_path.name}')
    elif room.get('image'):
        embed.set_image(url=room['image'])
    kwargs = {'embed': embed, 'view': RoomView(engine, content, *key), 'ephemeral': True}
    if file:
        kwargs['file'] = file
    await interaction.response.send_message(**kwargs)
