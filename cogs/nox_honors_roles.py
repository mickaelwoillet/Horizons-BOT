"""Synchronisation des sept distinctions NOX avec des rôles Discord existants."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .nox_honors import honorary_titles
from .nox_refuge import DB
from . import nox_refuge_engine as engine

ROLE_NAMES = {
    "premier_calin": "💛 Premier câlin cosmique",
    "gardien_biscuits": "🍪 Gardien des biscuits",
    "fontaine_etoiles": "💧 Fontaine d'étoiles",
    "complice_jeu": "🎮 Complice des bêtises",
    "calin_intergalactique": "🫶 Câlineur intergalactique",
    "ami_refuge": "🌟 Ami fidèle du Refuge",
    "pilier_refuge": "🏅 Pilier du Refuge",
}


def _can_manage(guild: discord.Guild) -> bool:
    me = guild.me
    return bool(me and me.guild_permissions.manage_roles)


async def sync_member(member: discord.Member) -> tuple[int, list[str]]:
    """Ajoute seulement les titres acquis, sans retirer de rôles existants."""
    guild = member.guild
    if not _can_manage(guild):
        return 0, ["Permission Gérer les rôles manquante"]
    with engine.connect(DB) as con:
        earned = {x["id"] for x in honorary_titles(con, guild.id, member.id)["earned"]}
    me = guild.me
    roles = {key: discord.utils.get(guild.roles, name=name) for key, name in ROLE_NAMES.items()}
    eligible = [
        role for key, role in roles.items()
        if key in earned and role is not None and role not in member.roles
        and not role.managed and role < me.top_role
    ]
    errors = []
    if eligible:
        try:
            await member.add_roles(*eligible, reason="Distinctions NOX acquises au Refuge")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"Attribution impossible : {type(exc).__name__}")
            return 0, errors
    return len(eligible), errors


class NoxHonorRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxroles(self, interaction: discord.Interaction, action: app_commands.Choice[str], debut: app_commands.Range[int, 0, 100000] = 0):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande réservée au serveur.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Réservé aux administrateurs et au fondateur.", ephemeral=True)
            return
        if not _can_manage(interaction.guild):
            await interaction.response.send_message(
                "Le bot doit avoir la permission **Gérer les rôles**.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if action.value == "installer":
            created, existing, failed = [], [], []
            for name in ROLE_NAMES.values():
                role = discord.utils.get(guild.roles, name=name)
                if role:
                    existing.append(name)
                    continue
                try:
                    role = await guild.create_role(
                        name=name, colour=discord.Colour.from_rgb(212, 175, 55),
                        hoist=False, mentionable=False,
                        reason="Distinctions honorifiques de NOX")
                    created.append(role.name)
                except (discord.Forbidden, discord.HTTPException):
                    failed.append(name)
            await interaction.followup.send(
                f"🐾 Rôles NOX : **{len(created)} créés**, **{len(existing)} déjà présents**, "
                f"**{len(failed)} échecs**.\\n"
                "Les nouveaux rôles doivent rester sous le rôle du bot dans la hiérarchie. "
                "Utilise ensuite `/noxroles synchroniser` pour les contributions passées.",
                ephemeral=True)
            return
        with engine.connect(DB) as con:
            user_ids = [row[0] for row in con.execute(
                "SELECT DISTINCT user_id FROM nox_refuge_contributions "
                "WHERE guild_id=? ORDER BY user_id LIMIT 101 OFFSET ?", (guild.id, debut)).fetchall()]
        count = 0
        processed = 0
        for uid in user_ids[:100]:
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            added, _ = await sync_member(member)
            count += added
            processed += 1
        await interaction.followup.send(
            f"🐾 Synchronisation : **{processed} membres examinés**, **{count} rôles attribués**."
            + (f" Suite : `/noxroles synchroniser debut:{debut + 100}`." if len(user_ids) > 100 else ""),
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxHonorRoles(bot))
