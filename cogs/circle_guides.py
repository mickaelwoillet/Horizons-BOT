"""Guides permanents des Cercles HORIZONS."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import CIRCLE_PROPOSALS_CHANNEL_ID, CIRCLES_CHANNEL_ID
from cogs.embed_theme import horizons_embed
from .storage import db
from .circle_proposals import CircleProposalEntry

log = logging.getLogger(__name__)
GUIDE_KEY = "circles_horizons_v1"


class CircleGuides(commands.Cog):
    """Publie ou actualise les deux guides permanents des Cercles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        with db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS circle_guide_publications (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    guide_key TEXT NOT NULL,
                    message_id INTEGER,
                    thread_id INTEGER,
                    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, channel_id, guide_key)
                )
                """
            )

    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self, "_guide_refreshed", False):
            return
        self._guide_refreshed = True
        # Ne pas créer de nouveau panneau au démarrage : ne mettre à jour que
        # celui déjà suivi dans la base, pour éviter tout doublon.
        with db() as conn:
            row = conn.execute(
                "SELECT message_id FROM circle_guide_publications WHERE channel_id=? AND guide_key='proposer_un_cercle'",
                (CIRCLE_PROPOSALS_CHANNEL_ID,),
            ).fetchone()
        if not row or not row[0]:
            log.info("Guide Cercle non suivi : commande /publier_guides_cercles nécessaire une fois")
            return
        channel = await self.resolve_channel(CIRCLE_PROPOSALS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(int(row[0]))
            proposal, _ = self.build_guides()
            if not proposal.thumbnail.url:
                proposal.set_thumbnail(url=self.bot.user.display_avatar.url)
            await message.edit(embed=proposal, view=CircleProposalEntry(), allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Actualisation du guide Cercle impossible")

    def build_guides(self) -> tuple[discord.Embed, discord.Embed]:
        proposal = horizons_embed(
            title="💡 Proposer un Cercle HORIZONS",
            description=(
                "Une passion, un centre d'intérêt ou une idée d'activité à partager ? "
                "Tu peux proposer la création d'un Cercle et aider à faire grandir la communauté.\n\n"
                "**Tous les membres peuvent faire une proposition.** Tu n'as pas besoin d'être membre du staff."
            ),
            color=discord.Color.gold(),
        )
        proposal.add_field(
            name="📝 Comment proposer ton idée ?",
            value="Clique sur **Proposer un Cercle** ci-dessous. Un formulaire privé te permettra de présenter ton idée à l'équipe, sans publier de message dans ce salon.",
            inline=False,
        )
        proposal.add_field(
            name="🔎 Après ta proposition",
            value=(
                "L'équipe étudiera chaque idée. Elle pourra l'accepter, te demander une précision "
                "ou expliquer pourquoi elle ne peut pas être retenue pour le moment. "
                "La validation permet de vérifier que le projet respecte l'esprit et les règles de HORIZONS."
            ),
            inline=False,
        )
        proposal.add_field(
            name="💜 Quelques repères",
            value=(
                "• Une idée simple suffit : pas besoin d'un projet déjà parfaitement organisé.\n"
                "• Les Cercles doivent rester accueillants, inclusifs et respectueux.\n"
                "• La participation est libre : personne n'a à être présent tout le temps.\n"
                "• Aucun Cercle ne peut remplacer les espaces d'aide ou les procédures de signalement."
            ),
            inline=False,
        )
        proposal.set_footer(text="HORIZONS • Les belles idées prennent vie ensemble.")

        circles = horizons_embed(
            title="🌐 Les Cercles HORIZONS",
            description=(
                "Les Cercles sont de petits espaces communautaires réunis autour d'un intérêt, "
                "d'une passion ou d'une envie de partager. Ils sont proposés par les membres "
                "et ouverts après validation de l'équipe."
            ),
            color=discord.Color.gold(),
        )
        circles.add_field(
            name="🧭 Comment découvrir les Cercles ?",
            value=(
                "Chaque Cercle validé sera présenté dans une publication dédiée avec son thème, "
                "son objectif, ses activités et les modalités pour le rejoindre. "
                "Parcours les publications et choisis librement celles qui t'intéressent."
            ),
            inline=False,
        )
        circles.add_field(
            name="🤝 Comment participer ?",
            value=(
                "Suis les indications de la publication du Cercle : manifeste ton intérêt, "
                "réponds au sujet ou contacte la personne qui l'anime si cela est indiqué. "
                "Tu peux rejoindre plusieurs Cercles, en quitter un ou faire une pause quand tu le souhaites."
            ),
            inline=False,
        )
        circles.add_field(
            name="🌱 L'esprit des Cercles",
            value=(
                "Bienveillance, respect, curiosité et liberté de participation. "
                "Les échanges écrits comptent autant que les rencontres vocales. "
                "Aucune présence régulière n'est obligatoire et chacun avance à son rythme."
            ),
            inline=False,
        )
        circles.add_field(
            name="💡 Tu as une idée ?",
            value=f"Propose ton propre Cercle dans <#{CIRCLE_PROPOSALS_CHANNEL_ID}>. "
                  "L'équipe l'étudiera avant toute ouverture.",
            inline=False,
        )
        circles.set_footer(text="HORIZONS • Des centres d'intérêt différents, des liens en commun.")
        return proposal, circles

    async def resolve_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None
        if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            return channel
        return None

    async def publish_or_update(
        self, guild: discord.Guild, channel_id: int, guide_key: str,
        embed: discord.Embed, forum_post_name: str,
    ) -> str:
        channel = await self.resolve_channel(channel_id)
        if channel is None:
            return f"<#{channel_id}> : salon introuvable ou type non pris en charge."

        with db() as conn:
            row = conn.execute(
                "SELECT message_id, thread_id FROM circle_guide_publications "
                "WHERE guild_id=? AND channel_id=? AND guide_key=?",
                (guild.id, channel_id, guide_key),
            ).fetchone()

        message = None
        thread = None
        if row:
            message_id, thread_id = row[0], row[1]
            if isinstance(channel, discord.ForumChannel) and thread_id:
                try:
                    thread = await self.bot.fetch_channel(int(thread_id))
                    if message_id:
                        message = await thread.fetch_message(int(message_id))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException, AttributeError):
                    thread = None
                    message = None
            elif isinstance(channel, discord.TextChannel) and message_id:
                try:
                    message = await channel.fetch_message(int(message_id))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message = None

        try:
            if message is not None:
                await message.edit(embed=embed, view=CircleProposalEntry() if guide_key == "proposer_un_cercle" else None, allowed_mentions=discord.AllowedMentions.none())
            elif isinstance(channel, discord.ForumChannel):
                created = await channel.create_thread(
                    name=forum_post_name[:100],
                    content="Guide permanent — merci de consulter cette présentation avant de participer.",
                    embeds=[embed],
                    view=CircleProposalEntry() if guide_key == "proposer_un_cercle" else None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                thread = created.thread
                message = created.message
            else:
                message = await channel.send(
                    embed=embed,
                    view=CircleProposalEntry() if guide_key == "proposer_un_cercle" else None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.exception("Publication du guide Cercle impossible dans le salon %s", channel_id)
            return f"<#{channel_id}> : publication impossible ({type(exc).__name__})."

        with db() as conn:
            conn.execute(
                """
                INSERT INTO circle_guide_publications
                    (guild_id, channel_id, guide_key, message_id, thread_id, published_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, channel_id, guide_key) DO UPDATE SET
                    message_id=excluded.message_id,
                    thread_id=excluded.thread_id,
                    published_at=CURRENT_TIMESTAMP
                """,
                (guild.id, channel_id, guide_key, message.id, thread.id if thread else None),
            )
        return f"<#{channel_id}> : {'message actualisé' if row else 'message publié'}."

    @app_commands.command(
        name="publier_guides_cercles",
        description="Publier ou actualiser les deux guides permanents des Cercles HORIZONS.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def publier_guides_cercles(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée depuis le serveur HORIZONS.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        proposal, circles = self.build_guides()
        results = await self.publish_or_update(
            interaction.guild, CIRCLE_PROPOSALS_CHANNEL_ID,
            "proposer_un_cercle", proposal, "📌 Fonctionnement — Proposer un Cercle",
        )
        results2 = await self.publish_or_update(
            interaction.guild, CIRCLES_CHANNEL_ID,
            "cercles_horizons", circles, "📌 Fonctionnement des Cercles HORIZONS",
        )
        await interaction.followup.send(
            "Guides des Cercles HORIZONS :\n" + results + "\n" + results2,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CircleGuides(bot))
