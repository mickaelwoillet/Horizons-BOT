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


def item_label(item):
    """Readable French label; never change the stored identifier."""
    names = {
        'poussiere_du_temps': 'Poussière du temps',
        'archives_assemblage_central': 'Assemblage central des archives',
    }
    if item in names:
        return names[item]
    label = item.replace('_', ' ')
    label = __import__('re').sub(r'\bfragment (\d+)\b', r'fragment n° \1', label)
    return label[:1].upper() + label[1:]


def inventory_category(item, room_id):
    """Presentation-only categories: no changes to game rules or inventory."""
    if any(word in item.lower() for word in ('souvenir', 'memoire', 'memory', 'echo')):
        return '🌠 Souvenirs et découvertes spéciales'
    if item.startswith(room_id + '_'):
        return '📍 Objets de la salle actuelle'
    return '🗃️ Objets conservés des autres salles'


def room_requirements(room, state):
    """Actionable, spoiler-light requirements based on actual engine prerequisites."""
    puzzles = room.get('puzzles', [])
    lock = next((p for p in puzzles if p.get('next_room') or p.get('finish') or p.get('finished')),
                puzzles[-1] if puzzles else None)
    if not lock:
        return 'Aucun verrou dans cette salle.'
    solved = set(state['solved'])
    items = set(state['items'])
    pending = [p for p in lock.get('requires_solved', []) if p not in solved]
    missing = [i for i in lock.get('requires', []) if i not in items]
    lines = [
        f"{'✅' if not pending else '⬜'} Épreuves préalables : **{len(lock.get('requires_solved', []))-len(pending)}/{len(lock.get('requires_solved', []))}**",
        f"{'✅' if not missing else '⬜'} Objets et mécanismes : **{len(lock.get('requires', []))-len(missing)}/{len(lock.get('requires', []))}**",
    ]
    if pending:
        lines.append(f'🧠 Il reste **{len(pending)} énigme(s)** à résoudre via le menu des épreuves.')
    if missing:
        recipes = room.get('recipes', [])
        possible = [r for r in recipes if r.get('result') in missing]
        if possible:
            for recipe in possible:
                ingredients = recipe.get('ingredients', [])
                held = [x for x in ingredients if x in items]
                if len(held) == len(ingredients):
                    lines.append('🧩 **Assemblage prêt !** Ouvre **Assembler** : '
                                 + ' + '.join(item_label(x) for x in ingredients) + '.')
                else:
                    lines.append('🧩 **Un assemblage est nécessaire** pour ouvrir le verrou. '
                                 f'Pièces réunies : {len(held)}/{len(ingredients)}. '
                                 'Examine le décor pour trouver les pièces manquantes.')
        non_recipe = [x for x in missing if not any(r.get('result') == x for r in recipes)]
        if non_recipe:
            lines.append(f'🔎 Il reste **{len(non_recipe)} élément(s)** à découvrir dans la salle.')
    if not pending and not missing:
        lines.append('🔓 **Tous les prérequis sont réunis : tu peux tenter le verrou !**')
    return '\n'.join(lines)


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
        if result.get('correct') and not result.get('already_solved'):
            # Fresh panel with updated checkmarks and newly unlocked puzzles.
            try:
                await show_room_followup(interaction, self.engine, self.content, self.key, transition=bool(result.get('next_room')))
            except (discord.HTTPException, discord.NotFound):
                pass
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



class NextRoomView(discord.ui.View):
    """A clear navigation affordance after the engine has unlocked the next room."""
    def __init__(self, engine, content, key):
        super().__init__(timeout=900)
        self.engine, self.content, self.key = engine, content, key

    async def interaction_check(self, interaction):
        # A transition panel can be reopened only by its owner or team members.
        if await reject_unauthorized(interaction, self.engine, self.key):
            return False
        if not self.engine.status(*self.key):
            await interaction.response.send_message(
                '⏳ Partie introuvable. Lance `/escape jouer` pour consulter tes parties.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Entrer dans la salle suivante', emoji='🚪', style=discord.ButtonStyle.success)
    async def enter(self, interaction, button):
        await show_room(interaction, self.engine, self.content, self.key)

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
            return await interaction.response.send_message('🔒 **Ce verrou n’est pas encore accessible.**\n' + room_requirements(self.room, state), ephemeral=True)
        description = puzzle.get('description', 'Observe attentivement la salle.')
        hints = len(puzzle.get('hints', []))
        await interaction.response.send_message(embed=discord.Embed(title=puzzle.get('title', 'Énigme'), description=description + '\n\n⏳ Si les boutons expirent, relance `/escape jouer` sans perdre ta progression.', color=0xc6993f), view=PuzzleActions(self.engine, self.content, self.key, puzzle), ephemeral=True)


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
    def __init__(self, view, position):
        self.position = position
        start = view.page * 25
        items = view.items[start:start + 25]
        super().__init__(
            placeholder=f'{position}ᵉ objet — page {view.page + 1}/{view.page_count}',
            row=position - 1,
            options=[discord.SelectOption(label=item_label(item)[:100], value=item)
                     for item in items])

    async def callback(self, interaction):
        view = self.view
        if await reject_unauthorized(interaction, view.engine, view.key):
            return
        state = view.engine.status(*view.key)
        if not state or state['room_id'] != view.room_id:
            return await interaction.response.send_message(
                '⏳ Cette interface a expiré. Relance `/escape jouer`.', ephemeral=True)
        item = self.values[0]
        if item not in state['items']:
            return await interaction.response.send_message(
                'Cet objet n’est plus dans ton inventaire.', ephemeral=True)
        view.selected[self.position] = item
        if len(view.selected) < 2:
            return await interaction.response.send_message(
                f'🎒 **{item_label(item)}** sélectionné. Choisis le second objet '
                '(tu peux changer de page).', ephemeral=True)
        first, second = view.selected[1], view.selected[2]
        view.selected.clear()
        try:
            result = view.engine.combine(*view.key, view.content, first, second)
        except AdventureError as exc:
            return await interaction.response.send_message(f'⚠️ {exc}', ephemeral=True)
        if result.get('combined'):
            # Consumed ingredients must not remain selectable in a stale menu.
            updated = view.engine.status(*view.key)
            remaining = updated['items'] if updated else []
            if len(remaining) >= 2 and updated['room_id'] == view.room_id:
                fresh = IngredientView(view.engine, view.content, view.key,
                                       remaining, view.room_id)
                await interaction.response.edit_message(
                    content='✅ ' + combine_feedback(result) +
                            '\n\n🧩 Inventaire actualisé : tu peux effectuer un autre assemblage.',
                    view=fresh)
            else:
                await interaction.response.edit_message(
                    content='✅ ' + combine_feedback(result) +
                            '\n\n🎒 Inventaire actualisé. Retourne au panneau de la salle.',
                    view=None)
            try:
                await show_room_followup(interaction, view.engine, view.content, view.key)
            except (discord.HTTPException, discord.NotFound):
                pass
        else:
            await interaction.response.send_message(combine_feedback(result), ephemeral=True)


class IngredientView(discord.ui.View):
    def __init__(self, engine, content, key, items, room_id, page=0, selected=None):
        super().__init__(timeout=900)
        self.engine, self.content, self.key = engine, content, key
        self.room_id = room_id
        self.items = sorted(items)
        self.page_count = max(1, (len(self.items) + 24) // 25)
        self.page = min(max(0, page), self.page_count - 1)
        self.selected = selected or {}
        self.add_item(IngredientPicker(self, 1))
        self.add_item(IngredientPicker(self, 2))
        if self.page_count > 1:
            previous = discord.ui.Button(label='◀ Page précédente', style=discord.ButtonStyle.secondary, row=2,
                                         disabled=self.page == 0)
            following = discord.ui.Button(label='Page suivante ▶', style=discord.ButtonStyle.secondary, row=2,
                                          disabled=self.page == self.page_count - 1)
            async def move(interaction, direction):
                if await reject_unauthorized(interaction, self.engine, self.key):
                    return
                state = self.engine.status(*self.key)
                if not state or state['room_id'] != self.room_id:
                    return await interaction.response.send_message(
                        '⏳ Relance `/escape jouer` pour actualiser cet assemblage.', ephemeral=True)
                new_view = IngredientView(self.engine, self.content, self.key,
                                          state['items'], self.room_id,
                                          self.page + direction, dict(self.selected))
                await interaction.response.edit_message(view=new_view)
            previous.callback = lambda interaction: move(interaction, -1)
            following.callback = lambda interaction: move(interaction, 1)
            self.add_item(previous)
            self.add_item(following)


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
        if result['new_items']:
            try:
                await show_room_followup(interaction, self.engine, self.content, self.key)
            except (discord.HTTPException, discord.NotFound):
                pass


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
        room = room_for(self.content, state) if state else None
        room_id = room['id'] if room else ''
        groups = {}
        for item in items:
            category = inventory_category(item, room_id)
            groups.setdefault(category, []).append(item)
        embed = discord.Embed(
            title='🎒 Inventaire', color=0xc6993f,
            description=(f'**{len(items)} objet(s)** récupéré(s). '
                         'Les objets restent disponibles pour les énigmes et assemblages.'))
        # Discord limite les embeds à 25 champs et 6000 caractères au total.
        # Regrouper les objets en lignes compactes évite les listes illisibles.
        field_count = 0
        for title, group in sorted(groups.items(), key=lambda pair: (0 if pair[0].startswith('📍') else 1, pair[0])):
            lines = [f'• {item_label(x)}' for x in group]
            chunk = ''
            part = 1
            for line in lines:
                if len(chunk) + len(line) + 1 > 950:
                    if field_count < 22:
                        embed.add_field(name=title if part == 1 else f'{title} (suite {part})',
                                        value=chunk, inline=False)
                        field_count += 1
                    chunk = ''
                    part += 1
                chunk += line + '\n'
            if chunk and field_count < 22:
                embed.add_field(name=title if part == 1 else f'{title} (suite {part})',
                                value=chunk, inline=False)
                field_count += 1
        if room:
            embed.add_field(name='🧩 Prochaine action', value=room_requirements(room, state)[:1024], inline=False)
        if not items:
            embed.description = 'Ton inventaire est vide. Examine le décor pour découvrir des objets.'
        elif len(items) > 25:
            embed.set_footer(text='Le menu Assembler propose désormais des pages pour tous tes objets.')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='Assembler', style=discord.ButtonStyle.secondary, emoji='🧩', row=1)
    async def assemble(self, interaction, button):
        state = self.engine.status(*self.key)
        if not state:
            return await interaction.response.send_message('Aucune partie active.', ephemeral=True)
        items = state['items']
        if len(items) < 2:
            return await interaction.response.send_message(
                '🎒 Il te faut au moins deux objets pour tenter un assemblage.', ephemeral=True)
        await interaction.response.send_message(
            '🧩 Choisis un objet dans chaque menu. Les deux objets seront assemblés si une recette existe dans cette salle.\n\n⏳ **Après 15 minutes d’inactivité**, relance `/escape jouer` : ton inventaire et ta progression sont conservés.',
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
    embed.add_field(name='🔒 Conditions du verrou', value=room_requirements(room, state), inline=False)
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


async def show_room_followup(interaction, engine, content, key, transition=False):
    """Post a new panel after a modal has already acknowledged its interaction."""
    state = engine.status(*key)
    room = room_for(content, state) if state else None
    if not room:
        return
    scene = engine.scene(*key, content)
    solved = sum(p['id'] in state['solved'] for p in room['puzzles'])
    embed = discord.Embed(title=('🚪 Nouvelle salle accessible — ' if transition else '🔄 Salle actualisée — ') + room['title'],
                          description=f'✅ **{solved}/{len(room["puzzles"])}** épreuves réussies\n\n⏳ Boutons expirés ? Relance `/escape jouer` : la sauvegarde reste intacte.', color=0xc6993f)
    embed.add_field(name='🔒 Conditions du verrou', value=room_requirements(room, state), inline=False)
    if state.get('completed'):
        embed.add_field(name='🏆 Aventure terminée', value='Félicitations !', inline=False)
    await interaction.followup.send(embed=embed, view=None if state.get('completed') else (NextRoomView(engine, content, key) if transition else RoomView(engine, content, *key)), ephemeral=True)
