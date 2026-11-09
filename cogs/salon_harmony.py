"""Harmonisation ciblée de salons existants, sans création de salon.

Les panneaux sont identifiés en SQLite et récupérés dans l'historique si besoin.
"""
from __future__ import annotations
import logging
import discord
from discord.ext import commands
from config import (GUILD_ID, AFFINITY_CHANNEL_ID, MOOD_CHANNEL_ID,
                    IDEAS_CHANNEL_ID, SOLIDARITY_CHANNEL_ID,
                    FIND_PARTNER_CHANNEL_ID, COLLECTIVE_CHALLENGES_CHANNEL_ID)
from .storage import db
from .embed_theme import wait_for_logo_ready, horizons_embed

log = logging.getLogger(__name__)
# Identifiants constants : aucun salon ni permission n'est recréé.
NAMES = {
    AFFINITY_CHANNEL_ID: '🧩・connexions-du-ciel',
    MOOD_CHANNEL_ID: '💗・meteo-des-emotions',
    IDEAS_CHANNEL_ID: '💡・boite-a-idees',
    SOLIDARITY_CHANNEL_ID: '💜・eclats-de-reconnaissance',
    FIND_PARTNER_CHANNEL_ID: '🤝・activites-ensemble',
    COLLECTIVE_CHALLENGES_CHANNEL_ID: '🌟・defis-collectifs',
}

EXPLANATIONS = {
    FIND_PARTNER_CHANNEL_ID: (
        '🤝 Activités ensemble · Rencontres amicales',
        'Propose directement une activité dans ce salon, ou découvre les annonces encore ouvertes.\n\n'
        'Choisis **Proposer une activité** pour créer une annonce avec le bouton « Ça m’intéresse ». '
        'Le bouton **Voir les activités ouvertes** affiche les invitations disponibles.\n\n'
        'Participation libre, respect des limites et des règles du serveur.'
    ),
    COLLECTIVE_CHALLENGES_CHANNEL_ID: (
        '🌟 Défis collectifs · Ensemble, plus loin',
        'Consulte le défi collectif en cours, suis sa progression et rejoins-le directement avec les boutons.\n\n'
        'Le défi quotidien est également accessible ici. Il est indépendant du défi collectif.\n\n'
        'Aucune obligation de participer et aucun classement entre membres.'
    ),
}

class ActivitySalonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Proposer une activité", emoji="✨", style=discord.ButtonStyle.primary,
                       custom_id="horizons:salon:activities:propose")
    async def propose(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .today_hub import ActivityProposalView
        await interaction.response.send_message("Choisis l'activité que tu souhaites proposer :", view=ActivityProposalView(), ephemeral=True)

    @discord.ui.button(label="Voir les activités ouvertes", emoji="📋", style=discord.ButtonStyle.secondary,
                       custom_id="horizons:salon:activities:list")
    async def list_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild_id is None:
            await interaction.response.send_message("Réservé au serveur.", ephemeral=True)
            return
        from .experiences import iso_now
        with db() as conn:
            rows = conn.execute(
                "SELECT activity,details,message_id,channel_id,thread_id,expires_at FROM activity_requests "
                "WHERE guild_id=? AND status='open' AND expires_at>? AND message_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 8", (interaction.guild_id, iso_now())
            ).fetchall()
        if not rows:
            await interaction.response.send_message("Aucune activité ouverte pour le moment. Tu peux en proposer une !", ephemeral=True)
            return
        lines = []
        for row in rows:
            channel_id = int(row['thread_id'] or row['channel_id'])
            jump = f"https://discord.com/channels/{interaction.guild_id}/{channel_id}/{int(row['message_id'])}"
            title = discord.utils.escape_markdown(str(row['activity'])[:70])
            lines.append(f"• **{title}** — [Voir l'annonce]({jump})")
        await interaction.response.send_message("**🤝 Activités ouvertes**\n" + "\n".join(lines), ephemeral=True,
                                                allowed_mentions=discord.AllowedMentions.none())


class CollectiveSalonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Voir le défi collectif", emoji="🌟", style=discord.ButtonStyle.primary,
                       custom_id="horizons:salon:collective:see")
    async def see(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Experiences")
        if cog is None:
            await interaction.response.send_message("Défis momentanément indisponibles.", ephemeral=True)
            return
        await cog.defi_collectif.callback(cog, interaction)

    @discord.ui.button(label="Rejoindre le défi", emoji="🙌", style=discord.ButtonStyle.success,
                       custom_id="horizons:salon:collective:join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Experiences")
        if cog is None:
            await interaction.response.send_message("Défis momentanément indisponibles.", ephemeral=True)
            return
        await cog.rejoindre_defi.callback(cog, interaction)

    @discord.ui.button(label="Défi du jour", emoji="🌱", style=discord.ButtonStyle.secondary,
                       custom_id="horizons:salon:collective:daily")
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("TodayHub")
        if cog is None:
            await interaction.response.send_message("Défi quotidien indisponible.", ephemeral=True)
            return
        await cog.show_daily_challenge(interaction)


class SalonHarmony(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._done = False

    async def cog_load(self):
        self.bot.add_view(ActivitySalonView())
        self.bot.add_view(CollectiveSalonView())

    @commands.Cog.listener()
    async def on_ready(self):
        if self._done:
            return
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        await wait_for_logo_ready()
        # La nouvelle identité visuelle prime sur les anciens noms V7.
        # Les panneaux interactifs restent gérés ici, sans conflit de renommage.
        visual_names = set(NAMES)
        try:
            from .visual_identity import load_config
            cfg = load_config()
            if cfg.get("enabled", False) and cfg.get("manage_channel_names", False):
                visual_names = {int(k) for k in cfg.get("channel_names", {})}
        except (OSError, ValueError):
            log.warning("Configuration visuelle indisponible, anciens noms conservés")
        # Les salons sont renommés une seule fois par configuration souhaitée.
        # Aucun renommage de catégorie ou modification de permissions.
        for channel_id, desired in NAMES.items():
            if not channel_id:
                continue
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                log.warning('Harmonisation ignorée : salon textuel %s introuvable.', channel_id)
                continue
            if channel_id not in visual_names and channel.name != desired:
                try:
                    await channel.edit(name=desired, reason='HORIZONS V7 : harmonisation des noms de salons')
                except (discord.Forbidden, discord.HTTPException):
                    log.exception('Impossible de renommer le salon %s.', channel_id)
            if channel_id in EXPLANATIONS:
                await self.ensure_panel(channel, *EXPLANATIONS[channel_id])
        self._done = True

    async def ensure_panel(self, channel: discord.TextChannel, title: str, description: str):
        embed = horizons_embed(title=title, description=description)
        embed.set_footer(text='HORIZONS • Panneau interactif permanent')
        view = ActivitySalonView() if channel.id == FIND_PARTNER_CHANNEL_ID else CollectiveSalonView()
        key = f'v7_harmony_panel_{channel.id}'
        with db() as conn:
            row = conn.execute('SELECT value FROM bot_settings WHERE key=?', (key,)).fetchone()
        message = None
        if row:
            try:
                message = await channel.fetch_message(int(row['value']))
                if message.author.id != self.bot.user.id:
                    message = None
            except (ValueError, TypeError, discord.NotFound):
                pass
            except (discord.Forbidden, discord.HTTPException):
                return
        if message is None:
            try:
                async for candidate in channel.history(limit=150):
                    if candidate.author.id == self.bot.user.id and any(e.title == title for e in candidate.embeds):
                        message = candidate
                        break
            except (discord.Forbidden, discord.HTTPException):
                return
        try:
            if message is None:
                message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
            elif (not message.embeds or message.embeds[0].to_dict() != embed.to_dict()
                  or {component.custom_id for row in message.components for component in row.children if getattr(component, 'custom_id', None)}
                  != {component.custom_id for component in view.children if getattr(component, 'custom_id', None)}):
                await message.edit(embed=embed, view=view)
        except (discord.Forbidden, discord.HTTPException):
            log.exception('Panneau explicatif impossible dans %s.', channel.id)
            return
        with db() as conn:
            conn.execute('INSERT INTO bot_settings(key,value) VALUES(?,?) '
                         'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(message.id)))
        # Migration ciblée des anciens panneaux statiques du bot. La suppression
        # intervient uniquement après création/récupération du panneau interactif.
        legacy_titles = {
            FIND_PARTNER_CHANNEL_ID: {"✦ Cherche quelqu'un pour partager une activité"},
            COLLECTIVE_CHALLENGES_CHANNEL_ID: {"✦ Défis collectifs HORIZONS"},
        }
        try:
            async for old in channel.history(limit=250):
                if old.id == message.id or old.author.id != self.bot.user.id:
                    continue
                if any(e.title in legacy_titles.get(channel.id, set()) for e in old.embeds):
                    await old.delete(reason="Migration HORIZONS : panneau statique remplacé par panneau interactif")
                    log.info("Ancien panneau statique supprimé : %s dans %s", old.id, channel.id)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Migration : ancien panneau non supprimé dans %s (permissions/historique)", channel.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(SalonHarmony(bot))
