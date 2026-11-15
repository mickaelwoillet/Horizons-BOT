"""Profil HORIZONS : panneau permanent à boutons et catégories éphémères."""
from __future__ import annotations
import json
import logging
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR, STAFF_ROLE_ID
from .embed_theme import horizons_embed

LOG = logging.getLogger(__name__)
CATALOG_PATH = DATA_DIR / 'role_catalog.json'
SINGLE = {"Tranche d'âge", 'Pronoms', 'Messages privés', 'Région'}
# Identité et orientation peuvent se recouper : sélection multiple facultative.
EMOJIS = {'Région':'🌍',"Tranche d'âge":'🎂','Pronoms':'🗣️','Identité de genre':'🏳️‍⚧️',
          'Orientation sexuelle':'💞','Messages privés':'✉️','Langues':'🌐',
          'Cultures à partager ou découvrir':'🎨',"Centres d'intérêt":'✨',
          'Styles musicaux':'🎵','Jeux':'🎮','Communication':'💬',
          'Disponibilités':'🕒','Ce que je recherche':'🤝','Tempérament':'🌈','Notifications':'🔔'}

def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))

class ChoiceButton(discord.ui.Button):
    def __init__(self, category, name, rid, selected):
        super().__init__(label=name[:80], style=discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary,
                         emoji='✓' if selected else None)
        self.category, self.role_name, self.role_id = category, name, int(rid)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message('Disponible uniquement sur HORIZONS.', ephemeral=True)
        guild, member = interaction.guild, interaction.user
        role = guild.get_role(self.role_id)
        if role is None:
            return await interaction.response.send_message('Ce rôle n’est pas encore installé. Demande au staff d’utiliser /installer_roles.', ephemeral=True)
        me = guild.me
        if not me or not me.guild_permissions.manage_roles or role.managed or role >= me.top_role:
            return await interaction.response.send_message('Le bot ne peut pas attribuer ce rôle. Vérifie sa hiérarchie.', ephemeral=True)
        selected = role in member.roles
        old_roles = []
        if not selected and self.category in SINGLE:
            old_roles = [guild.get_role(int(rid)) for name, rid in catalog()[self.category] if int(rid) and int(rid) != role.id]
            old_roles = [r for r in old_roles if r in member.roles]
            legacy_path = DATA_DIR / 'role_legacy_ids.json'
            if legacy_path.exists():
                legacy_ids = json.loads(legacy_path.read_text(encoding='utf-8')).get(self.category, [])
                old_roles.extend(r for rid in legacy_ids if (r := guild.get_role(int(rid))) and r in member.roles and r != role and r not in old_roles)
            if any(r.managed or r >= me.top_role for r in old_roles):
                return await interaction.response.send_message('Un ancien rôle ne peut pas être retiré par le bot.', ephemeral=True)
        if self.category == 'Notifications' and not selected:
            options = catalog()[self.category]
            none = next((guild.get_role(int(rid)) for name, rid in options if name == 'Aucune notification' and int(rid)), None)
            if self.role_name == 'Aucune notification':
                old_roles = [guild.get_role(int(rid)) for name, rid in options if name != self.role_name and int(rid) and guild.get_role(int(rid)) in member.roles]
            elif none and none in member.roles:
                old_roles = [none]
        try:
            if old_roles:
                await member.remove_roles(*old_roles, reason='Profil HORIZONS : choix exclusif')
            if selected:
                await member.remove_roles(role, reason='Profil HORIZONS : désélection')
            else:
                await member.add_roles(role, reason='Profil HORIZONS : sélection')
        except discord.HTTPException:
            return await interaction.response.send_message('Modification impossible pour le moment. Réessaie.', ephemeral=True)
        await interaction.response.edit_message(
            content=f'{EMOJIS.get(self.category,"🎭")} **{self.category}** — clique pour ajouter ou retirer un rôle.\n'
                    f'**{self.role_name}** : {"retiré" if selected else "ajouté"} ✔',
            view=ChoicePage(self.category, self.view.page, member))

class PageButton(discord.ui.Button):
    def __init__(self, category, page, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=4)
        self.category, self.page = category, page
    async def callback(self, interaction):
        await interaction.response.edit_message(content=f'**{self.category}** — sélectionne les rôles souhaités.', view=ChoicePage(self.category,self.page,interaction.user))

class ChoicePage(discord.ui.View):
    def __init__(self, category, page, member):
        super().__init__(timeout=900)
        self.page = page
        options = catalog()[category]
        ids = {r.id for r in member.roles}
        start = page*20
        for name, rid in options[start:start+20]:
            self.add_item(ChoiceButton(category,name,rid,int(rid) in ids))
        if page:
            self.add_item(PageButton(category,page-1,'◀ Précédent'))
        if start+20 < len(options):
            self.add_item(PageButton(category,page+1,'Suivant ▶'))

class CategoryButton(discord.ui.Button):
    def __init__(self, category, idx):
        super().__init__(label=category[:80], emoji=EMOJIS.get(category), style=discord.ButtonStyle.secondary,
                         custom_id=f'horizons:profile:category:{idx}')
        self.category = category
    async def callback(self, interaction):
        if not isinstance(interaction.user,discord.Member):
            return await interaction.response.send_message('Disponible sur le serveur uniquement.',ephemeral=True)
        await interaction.response.send_message(f'**{self.category}** — clique pour ajouter ou retirer un rôle.',
                                                view=ChoicePage(self.category,0,interaction.user),ephemeral=True)

class ProfileHub(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for idx, category in enumerate(catalog()):
            self.add_item(CategoryButton(category,idx))

class RolePanels(commands.Cog):
    def __init__(self,bot): self.bot=bot
    async def cog_load(self): self.bot.add_view(ProfileHub())

    @app_commands.command(name='installer_roles',description='Créer les rôles de profil manquants et actualiser le panneau (administration).')
    @app_commands.default_permissions(manage_roles=True)
    async def installer_roles(self, interaction: discord.Interaction):
        if not isinstance(interaction.user,discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message('Commande réservée aux administrateurs.',ephemeral=True)
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message('Le bot doit avoir la permission Gérer les rôles.',ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        data=catalog(); created=[]; existing={r.name:r for r in interaction.guild.roles}
        for category, options in data.items():
            for entry in options:
                name,rid=entry
                if rid and interaction.guild.get_role(int(rid)):continue
                role=existing.get(name)
                if role is None:
                    try:
                        role=await interaction.guild.create_role(name=name,mentionable=False,hoist=False,
                                                                 reason=f'HORIZONS : profil {category}')
                    except discord.HTTPException as exc:
                        CATALOG_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                        return await interaction.followup.send(f'Installation interrompue sur **{name}** : {exc}. {len(created)} rôles créés, IDs sauvegardés.',ephemeral=True)
                    created.append(name)
                entry[1]=role.id
                existing[name]=role
        CATALOG_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        await interaction.followup.send(f'✅ {len(created)} nouveaux rôles créés ; catalogue actualisé. Utilise `/publier_roles` dans le salon des rôles pour afficher le panneau.',ephemeral=True)

    @app_commands.command(name='publier_roles',description='Publier le panneau unique de personnalisation du profil HORIZONS.')
    @app_commands.default_permissions(manage_guild=True)
    async def publier_roles(self,interaction:discord.Interaction):
        if not isinstance(interaction.user,discord.Member) or not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message('Commande réservée au staff.',ephemeral=True)
        if not isinstance(interaction.channel,discord.TextChannel):
            return await interaction.response.send_message('Utilise un salon textuel.',ephemeral=True)
        missing=sum(1 for options in catalog().values() for _,rid in options if not rid or not interaction.guild.get_role(int(rid)))
        if missing:
            return await interaction.response.send_message(f'{missing} rôles restent à installer. Lance d’abord `/installer_roles`.',ephemeral=True)
        embed=horizons_embed(title='🎭 Mon profil HORIZONS',description='Choisis une rubrique ci-dessous. Les boutons ouvrent des choix **privés**, modifiables à tout moment.\n\nLes informations personnelles sont entièrement facultatives.',color=discord.Color.gold())
        embed.set_footer(text='HORIZONS • Unis dans la diversité')
        await interaction.response.defer(ephemeral=True)
        # Retirer seulement les anciens panneaux répertoriés dans SQLite, jamais les messages des membres.
        from .storage import db
        with db() as conn:
            rows=conn.execute('SELECT channel_id,message_id FROM role_panels WHERE channel_id=?',(interaction.channel.id,)).fetchall()
        for row in rows:
            try:
                msg=await interaction.channel.fetch_message(row['message_id'])
                if msg.author.id == self.bot.user.id: await msg.delete()
            except discord.HTTPException: pass
        message=await interaction.channel.send(embed=embed,view=ProfileHub())
        with db() as conn:
            conn.execute('DELETE FROM role_panels WHERE channel_id=?',(interaction.channel.id,))
            conn.execute('INSERT INTO role_panels(channel_id,message_id,category) VALUES(?,?,?)',(interaction.channel.id,message.id,'Profil HORIZONS'))
        await interaction.followup.send('✅ Panneau de profil publié. Les anciens panneaux enregistrés ont été remplacés.',ephemeral=True)

async def setup(bot):await bot.add_cog(RolePanels(bot))
