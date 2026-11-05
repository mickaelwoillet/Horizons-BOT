"""Charte HORIZONS et validation du rôle Membre par bouton persistant."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

import logging
import discord
from discord.ext import commands
from config import CHARTER_CHANNEL_ID, NEW_MEMBER_ROLE_ID, MEMBER_ROLE_ID

logger = logging.getLogger("horizons.onboarding")
CHARTER_MARKER = "HORIZONS_CHARTER_V1"


class AcceptCharterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="J'accepte le règlement", style=discord.ButtonStyle.success, emoji="✅", custom_id="horizons:accept_charter:v1")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Cette action est disponible uniquement sur le serveur HORIZONS.", ephemeral=True)
            return
        member = interaction.user
        guild = interaction.guild
        newcomer = guild.get_role(NEW_MEMBER_ROLE_ID) if NEW_MEMBER_ROLE_ID else None
        verified = guild.get_role(MEMBER_ROLE_ID) if MEMBER_ROLE_ID else None
        if not verified:
            await interaction.response.send_message("Le rôle Membre est introuvable. Préviens l'équipe HORIZONS.", ephemeral=True)
            return
        if verified in member.roles:
            await interaction.response.send_message("Tu as déjà le rôle **Membre**. Bienvenue dans la communauté ! ✦", ephemeral=True)
            return
        bot_member = guild.me
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message("Je n'ai pas la permission de gérer les rôles. Préviens l'équipe.", ephemeral=True)
            return
        if verified >= bot_member.top_role or (newcomer and newcomer >= bot_member.top_role):
            await interaction.response.send_message("Je ne peux pas gérer ces rôles à cause de leur position dans la hiérarchie Discord. L'équipe doit placer mon rôle au-dessus des rôles Nouveau membre et Membre.", ephemeral=True)
            return
        try:
            await member.add_roles(verified, reason="Charte HORIZONS acceptée via le bouton")
            if newcomer and newcomer in member.roles:
                await member.remove_roles(newcomer, reason="Validation de la charte HORIZONS")
        except discord.Forbidden:
            await interaction.response.send_message("Discord a refusé la modification des rôles. Vérifie la permission Gérer les rôles et la hiérarchie du bot.", ephemeral=True)
            return
        except discord.HTTPException:
            logger.exception("Erreur lors de la validation de la charte pour %s", member.id)
            await interaction.response.send_message("Une erreur Discord est survenue. Réessaie dans quelques instants.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Merci d'avoir accepté la charte ! Ton rôle **Membre** vient de t'être attribué. Bienvenue officiellement sur HORIZONS ! 🌈", ephemeral=True)


class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._charter_ready = False

    async def cog_load(self):
        self.bot.add_view(AcceptCharterView())

    def build_charter(self) -> discord.Embed:
        embed = horizons_embed(
            title="✦ La charte HORIZONS",
            description=(
                "Bienvenue sur HORIZONS ! Cette communauté est un espace d'échange, de découverte, de partage et d'entraide. "
                "Pour que chacun puisse s'y sentir bien, merci de respecter les règles suivantes :"
            ),
            color=discord.Color.gold(),
        )
        rules = [
            ("✦ 1. Respect et bienveillance", "Respecte chaque personne. Les insultes, le harcèlement, les menaces, l'humiliation et les propos discriminatoires n'ont pas leur place ici."),
            ("🤝 2. Respect des limites", "Chacun est libre de participer ou non. Respecte les refus, ne force jamais une conversation et n'insiste pas après un non."),
            ("🔒 3. Vie privée et confidentialité", "Ne publie pas les informations personnelles d'autrui, ne partage pas de captures ou de conversations privées sans accord et protège également tes propres données."),
            ("💬 4. Échanges et messages privés", "Pas de spam, de publicité non autorisée, de démarchage ou de sollicitations répétées. Demande l'accord avant d'envoyer des messages privés."),
            ("🌿 5. Contenus adaptés", "Publie dans les salons appropriés. Les contenus illégaux, menaçants, pornographiques ou destinés à choquer ou à mettre quelqu'un mal à l'aise sont interdits."),
            ("🧭 6. Utilisation des salons", "Respecte le thème et les consignes de chaque salon. Évite le flood et suis les indications de l'équipe de modération."),
            ("🛡️ 7. Sécurité et modération", "Ne contourne pas les sanctions et ne cherche pas à déclencher des conflits. Si tu rencontres un problème, contacte l'équipe ou utilise les outils de signalement."),
            ("⚖️ 8. Respect du règlement", "L'équipe peut intervenir, supprimer un contenu ou appliquer une sanction proportionnée en cas de non-respect de la charte. Les décisions de modération doivent être respectées et peuvent être discutées calmement en privé."),
        ]
        for title, body in rules:
            embed.add_field(name=title, value=body, inline=False)
        embed.add_field(
            name="✅ Validation",
            value=("En cliquant sur **J'accepte le règlement**, tu confirmes avoir lu et accepté cette charte. "
                   "Le rôle **Membre** te sera attribué et le rôle **🌱 Nouveau membre** sera retiré."),
            inline=False,
        )
        embed.set_footer(text=f"HORIZONS • Charte communautaire • {CHARTER_MARKER}")
        return embed

    @commands.Cog.listener()
    async def on_ready(self):
        await wait_for_logo_ready()
        if self._charter_ready or not CHARTER_CHANNEL_ID:
            return
        self._charter_ready = True
        channel = self.bot.get_channel(CHARTER_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(CHARTER_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.exception("Salon de charte introuvable ou inaccessible (%s)", CHARTER_CHANNEL_ID)
                return
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.error("Le salon de charte %s n'est pas un salon textuel.", CHARTER_CHANNEL_ID)
            return
        try:
            async for message in channel.history(limit=100):
                if message.author.id == self.bot.user.id and any(CHARTER_MARKER in (e.footer.text or "") for e in message.embeds):
                    await message.edit(embed=self.build_charter(), view=AcceptCharterView())
                    logger.info("Charte HORIZONS actualisée dans le salon %s.", CHARTER_CHANNEL_ID)
                    return
            await channel.send(embed=self.build_charter(), view=AcceptCharterView())
            logger.info("Charte HORIZONS publiée dans le salon %s.", CHARTER_CHANNEL_ID)
        except discord.Forbidden:
            logger.error("Permissions insuffisantes pour publier la charte dans %s.", CHARTER_CHANNEL_ID)
        except discord.HTTPException:
            logger.exception("Impossible de publier la charte HORIZONS.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
