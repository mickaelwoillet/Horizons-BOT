"""Interface Discord des salles HORIZONS, réutilisable pour chaque aventure."""
from __future__ import annotations
import discord
import sqlite3
from pathlib import Path
from escape_engine import Engine, AdventureError
from escape_event_logs import log_escape_event
from escape_victory import celebrate


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
        state = self.engine.status(*self.key)
        room = room_for(self.content, state) if state else None
        if not room or self.puzzle['id'] not in {p['id'] for p in room['puzzles']}:
            return await interaction.response.send_message(
                '⏳ Cette énigme n’est plus dans la salle active. Utilise /escape jouer.', ephemeral=True)
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
        # The engine returns a transition only for the first successful solve.
        # Logging after the response keeps the interaction responsive.
        if result.get('finished'):
            await log_escape_event(interaction, 'finish', mode=self.key[2])
            await celebrate(interaction, self.engine.database, self.key,
                            secret=(room == self.content['rooms'][-1]))
        elif result.get('next_room'):
            room_id = result['next_room']
            for index, room in enumerate(self.content['rooms'], start=1):
                if room['id'] == room_id:
                    await log_escape_event(interaction, 'room', room_number=index,
                                           room_name=room.get('name', room.get('title', 'Salle inconnue')),
                                           mode=self.key[2])
                    break


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
        puzzle = next((p for p in self.room['puzzles'] if p['id'] == self.values[0]), None)
        if puzzle is None:
            return await interaction.response.send_message('Énigme introuvable.', ephemeral=True)
        access = self.engine.puzzle_access(*self.key, self.content, puzzle['id'])
        if not access['accessible']:
            return await interaction.response.send_message('🔒 Cette épreuve n’est pas encore accessible. Poursuis les découvertes précédentes.', ephemeral=True)
        description = puzzle.get('description', 'Observe attentivement la salle.')
        hints = len(puzzle.get('hints', []))
        await interaction.response.send_message(embed=discord.Embed(title=puzzle.get('title', 'Énigme'), description=description, color=0xc6993f), view=PuzzleActions(self.engine, self.content, self.key, puzzle), ephemeral=True)


class PuzzleActions(discord.ui.View):
    def __init__(self, engine, content, key, puzzle):
        super().__init__(timeout=900)  # Vue éphémère : Discord limite la durée de vie des composants.
        self.engine, self.content, self.key, self.puzzle = engine, content, key, puzzle

    async def interaction_check(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return False
        state = self.engine.status(*self.key)
        room = room_for(self.content, state) if state else None
        if not room or self.puzzle['id'] not in {p['id'] for p in room['puzzles']}:
            await interaction.response.send_message(
                'Cette énigme appartient à une ancienne salle. Utilise /escape jouer.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Répondre', style=discord.ButtonStyle.primary, emoji='🗝️')
    async def answer(self, interaction, button):
        await interaction.response.send_modal(AnswerModal(self.engine, self.content, *self.key, self.puzzle))

    @discord.ui.button(label='Rouvrir la salle', style=discord.ButtonStyle.secondary, emoji='🔄')
    async def reopen_room(self, interaction, button):
        # Open a fresh ephemeral view, reflecting the current saved state.
        # This is a convenience action while the puzzle panel is alive;
        # after Discord expires it, /escape jouer remains the recovery path.
        await show_room(interaction, self.engine, self.content, self.key)

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

    def __init__(self, engine, content, key, room_id=None):
        super().__init__()
        self.engine, self.content, self.key = engine, content, key
        self.room_id = room_id

    async def on_submit(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        state = self.engine.status(*self.key)
        if not state or (self.room_id is not None and state['room_id'] != self.room_id):
            return await interaction.response.send_message('⏳ Cet inventaire n’est plus à jour. Utilise /escape jouer.', ephemeral=True)
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


def combine_feedback(result):
    if result.get('combined'):
        return ('🧩 Assemblage déjà réalisé.' if result.get('already_created')
                else '🧩 Assemblage réussi ! Consulte ton inventaire.')
    if result.get('reason') == 'missing_items':
        return '🎒 Un des objets n’est plus dans ton inventaire. Rouvre la salle.'
    if result.get('reason') == 'same_item':
        return '⚠️ Choisis deux objets différents.'
    return '🔎 Ces objets ne semblent pas s’assembler ici.'


class IngredientPicker(discord.ui.Select):
    def __init__(self, engine, content, key, items, position):
        self.engine, self.content, self.key, self.position = engine, content, key, position
        super().__init__(placeholder=f'{position} objet à assembler', row=position - 1,
                         options=[discord.SelectOption(label=item[:100], value=item)
                                  for item in items[:25]])

    async def callback(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        state = self.engine.status(*self.key)
        if not state or state['room_id'] != self.view.room_id:
            return await interaction.response.send_message(
                'Cette interface n’est plus à jour. Utilise /escape jouer.', ephemeral=True)
        selected = self.values[0]
        if selected not in state['items']:
            return await interaction.response.send_message(
                'Cet objet n’est plus disponible. Rouvre l’inventaire.', ephemeral=True)
        self.view.selected[self.position] = selected
        if len(self.view.selected) < 2:
            return await interaction.response.send_message(
                f'🎒 Premier objet sélectionné : **{selected}**. Choisis maintenant le second.',
                ephemeral=True)
        first, second = self.view.selected[1], self.view.selected[2]
        self.view.selected.clear()
        try:
            result = self.engine.combine(*self.key, self.content, first, second)
        except AdventureError as exc:
            return await interaction.response.send_message(f'⚠️ {exc}', ephemeral=True)
        await interaction.response.send_message(combine_feedback(result), ephemeral=True)


class IngredientView(discord.ui.View):
    def __init__(self, engine, content, key, items, room_id):
        super().__init__(timeout=900)
        self.engine, self.content, self.key = engine, content, key
        self.room_id = room_id
        self.selected = {}
        self.add_item(IngredientPicker(engine, content, key, items, 1))
        self.add_item(IngredientPicker(engine, content, key, items, 2))

    async def interaction_check(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return False
        state = self.engine.status(*self.key)
        if not state or state['room_id'] != self.room_id:
            await interaction.response.send_message(
                '⏳ Cet assemblage appartient à une ancienne salle. Utilise `/escape jouer` pour rouvrir ta partie.',
                ephemeral=True)
            return False
        return True


class DecorPicker(discord.ui.Select):
    def __init__(self, engine, content, key, room):
        self.engine, self.content, self.key, self.room = engine, content, key, room
        options = [discord.SelectOption(label=h['title'][:100], value=h['id'])
                   for h in room.get('hotspots', [])[:25]]
        super().__init__(placeholder='🔎 Examiner un élément du décor', options=options, row=2)

    async def callback(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return
        state = self.engine.status(*self.key)
        if not state or state['room_id'] != self.room['id']:
            return await interaction.response.send_message(
                '⏳ Le décor a changé. Utilise /escape jouer.', ephemeral=True)
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
        super().__init__(timeout=900)  # Vue éphémère : Discord limite la durée de vie des composants.
        self.engine, self.content = engine, content
        self.key = (guild_id, adventure, mode, owner_id)
        state = engine.status(*self.key)
        room = room_for(content, state) if state else None
        self.room_id = state['room_id'] if state else None
        if room and room['puzzles']:
            self.add_item(PuzzlePicker(engine, content, self.key, room, state))
        if room and room.get('hotspots'):
            self.add_item(DecorPicker(engine, content, self.key, room))

    async def interaction_check(self, interaction):
        if await reject_unauthorized(interaction, self.engine, self.key):
            return False
        state = self.engine.status(*self.key)
        if not state:
            await interaction.response.send_message('⏳ Partie introuvable. Utilise `/escape jouer`.', ephemeral=True)
            return False
        if state['room_id'] != self.room_id:
            await interaction.response.send_message(
                '⏳ Cette interface appartient à une ancienne salle. Utilise `/escape jouer` pour retrouver ta salle actuelle.',
                ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Inventaire', style=discord.ButtonStyle.secondary, emoji='🎒', row=1)
    async def inventory(self, interaction, button):
        state = self.engine.status(*self.key)
        items = state['items'] if state else []
        await interaction.response.send_message('🎒 **Inventaire :** ' + (', '.join(items) if items else 'vide'), ephemeral=True)

    @discord.ui.button(label='Assembler', style=discord.ButtonStyle.secondary, emoji='🧩', row=1)
    async def assemble(self, interaction, button):
        state = self.engine.status(*self.key)
        if not state:
            return await interaction.response.send_message('Aucune partie active.', ephemeral=True)
        items = state['items']
        if len(items) < 2:
            return await interaction.response.send_message(
                '🎒 Il te faut au moins deux objets pour tenter un assemblage.', ephemeral=True)
        if len(items) > 25:
            return await interaction.response.send_modal(CombineModal(self.engine, self.content, self.key, state['room_id']))
        await interaction.response.send_message(
            '🧩 Choisis un objet dans chaque menu. Les deux objets seront assemblés si une recette existe dans cette salle.',
            view=IngredientView(self.engine, self.content, self.key, items, state['room_id']),
            ephemeral=True)

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
    embed.add_field(name='⏳ Reprendre après une pause', value='Les interfaces privées Discord peuvent expirer après 15 minutes. Relance **`/escape jouer`** dans le même mode (Solo ou Collectif) pour ouvrir des boutons neufs. Ta progression enregistrée est conservée.', inline=False)
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
