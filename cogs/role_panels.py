"""Panneaux de rôles HORIZONS, avec sélections persistantes."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import json
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR, STAFF_ROLE_ID
from .storage import db

CATALOG_PATH = DATA_DIR / "role_catalog.json"
SINGLE = {"Tranche d'âge", "Pronoms", "Identité de genre", "Orientation sexuelle", "Messages privés", "Région"}
DESCRIPTIONS = {
    "Tranche d'âge": "Choisis une seule tranche. Le choix est facultatif.",
    "Pronoms": "Choisis les pronoms que tu souhaites afficher. Une seule réponse.",
    "Identité de genre": "Choisis une seule réponse, ou ne réponds pas.",
    "Orientation sexuelle": "Question totalement facultative et personnelle. Ne choisis ce rôle que si tu souhaites l'afficher.",
    "Messages privés": "Indique clairement tes préférences. Ce rôle ne bloque pas techniquement les DM Discord.",
    "Langues": "Plusieurs réponses possibles.",
    "Cultures à partager ou découvrir": "Choisis les cultures que tu souhaites partager ou découvrir, sans avoir à déclarer tes origines.",
    "Région": "Choisis une seule zone générale. Aucune localisation précise n'est demandée.",
    "Centres d'intérêt": "Plusieurs réponses possibles.",
    "Styles musicaux": "Plusieurs réponses possibles.",
    "Jeux": "Plusieurs réponses possibles.",
    "Communication": "Plusieurs réponses possibles.",
    "Disponibilités": "Plusieurs réponses possibles.",
    "Ce que je recherche": "Plusieurs réponses possibles.",
    "Tempérament": "Plusieurs réponses possibles.",
    "Notifications": "Plusieurs réponses possibles. « Aucune notification » est exclusif des autres choix.",
}

def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

class RoleSelect(discord.ui.Select):
    def __init__(self, category: str, options: list[tuple[str, int]]):
        self.category = category
        self.role_options = options
        multi = category not in SINGLE
        super().__init__(
            placeholder=f"Choisir : {category}"[:150],
            min_values=0,
            max_values=len(options) if multi else 1,
            options=[discord.SelectOption(label=name[:100], value=str(role_id)) for name, role_id in options],
            custom_id=f"horizons:roles:{list(load_catalog()).index(category)}",
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Cette sélection est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        all_ids = {rid for _, rid in self.role_options}
        selected_ids = {int(value) for value in self.values}
        # « Aucune notification » annule les autres choix de notification, et inversement.
        if self.category == "Notifications":
            none_id = next((rid for label, rid in self.role_options if label == "Aucune notification"), None)
            if none_id in selected_ids:
                selected_ids = {none_id}
            elif selected_ids:
                selected_ids.discard(none_id)
        roles_by_id = {role.id: role for role in interaction.guild.roles}
        missing = [rid for rid in all_ids if rid not in roles_by_id]
        if missing:
            await interaction.followup.send(
                f"Certains rôles n'existent pas ou ne sont pas accessibles ({len(missing)}). Préviens l'équipe HORIZONS.",
                ephemeral=True,
            )
            return
        to_remove = [roles_by_id[rid] for rid in all_ids if rid in {r.id for r in interaction.user.roles} and rid not in selected_ids]
        to_add = [roles_by_id[rid] for rid in selected_ids if rid not in {r.id for r in interaction.user.roles}]
        try:
            if to_remove:
                await interaction.user.remove_roles(*to_remove, reason=f"Modification du profil : {self.category}")
            if to_add:
                await interaction.user.add_roles(*to_add, reason=f"Choix du profil : {self.category}")
        except discord.Forbidden:
            await interaction.followup.send("Je n'ai pas la permission de gérer ces rôles. Vérifie que mon rôle est placé au-dessus des rôles HORIZONS.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send("Discord n'a pas accepté la modification. Réessaie.", ephemeral=True)
            return
        # Le suivi d'accueil ne conserve aucun rôle ni choix personnel.
        # Il note seulement qu'un membre a personnalisé des préférences non sensibles.
        trackable_categories = {
            "Langues", "Cultures à partager ou découvrir", "Centres d'intérêt",
            "Styles musicaux", "Jeux", "Communication", "Disponibilités",
            "Tempérament", "Notifications",
        }
        if self.category in trackable_categories:
            with db() as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(onboarding_progress)").fetchall()}
                if "profile_customized" in columns:
                    conn.execute(
                        "UPDATE onboarding_progress SET profile_customized=1 WHERE guild_id=? AND user_id=?",
                        (interaction.guild.id, interaction.user.id),
                    )
        await interaction.followup.send("Tes rôles ont été mis à jour. 💜", ephemeral=True)

class RolePanelView(discord.ui.View):
    def __init__(self, category: str, options: list[tuple[str, int]]):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(category, options))

class RolePanels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Les custom_id sont uniques par catégorie : enregistrer les vues
        # globalement permet aux anciens panneaux de fonctionner même si
        # leurs identifiants de message ne figurent plus dans SQLite.
        catalog = load_catalog()
        for category, raw_options in catalog.items():
            options = [(label, int(role_id)) for label, role_id in raw_options]
            self.bot.add_view(RolePanelView(category, options))

    @app_commands.command(name="publier_roles", description="Publier les panneaux de choix des rôles HORIZONS dans ce salon.")
    async def publier_roles(self, interaction: discord.Interaction):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (
            member.guild_permissions.administrator or member.guild_permissions.manage_guild or
            (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles))
        )
        if not allowed:
            await interaction.response.send_message("Commande réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Utilise cette commande dans le salon textuel 🎭・choix-des-rôles.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        published = 0
        for category, raw_options in load_catalog().items():
            options = [(name, int(role_id)) for name, role_id in raw_options]
            embed = horizons_embed(
                title=f"🎭 {category}",
                description=DESCRIPTIONS.get(category, "Choisis les rôles qui correspondent à tes envies. Plusieurs réponses possibles.") + "\n\nTu peux modifier ton choix à tout moment.",
                color=discord.Color.from_rgb(145, 85, 220),
            )
            embed.set_footer(text="HORIZONS • Tes choix sont facultatifs")
            try:
                message = await interaction.channel.send(embed=embed, view=RolePanelView(category, options))
            except discord.HTTPException:
                await interaction.followup.send(f"Publication interrompue à la catégorie **{category}**. Vérifie les permissions du bot.", ephemeral=True)
                return
            with db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO role_panels(channel_id,message_id,category) VALUES(?,?,?)",
                    (interaction.channel.id, message.id, category),
                )
            published += 1
        await interaction.followup.send(f"✅ **{published} panneaux** de rôles ont été publiés dans {interaction.channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanels(bot))
