"""Commandes générales et informations HORIZONS."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from config import LOCAL_TIMEZONE, GUILD_ID

class General(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    @app_commands.command(name="ping", description="Vérifier si le bot HORIZONS répond.")
    async def ping(self, interaction: discord.Interaction):
        ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong ! Latence : **{ms} ms**", ephemeral=True)

    @app_commands.command(name="aide", description="Afficher le centre d'aide HORIZONS.")
    async def aide(self, interaction: discord.Interaction):
        embed = horizons_embed(
            title="✦ HORIZONS — Centre d'aide",
            description=(
                "Retrouve ici les principales commandes du serveur. "
                "Les commandes réservées à l'équipe ne sont utilisables que par les personnes habilitées."
            ),
            color=discord.Color.gold(),
        )
        sections = [
            (
                "👋 Membres",
                "`/ping` — vérifier la latence du bot.\n"
                "`/profil [membre]` — consulter un profil public.\n"
                "`/serveur` — découvrir les informations de HORIZONS.\n"
                "`/presentation` — retrouver le salon de présentation.\n"
                "`/proposer idee` — transmettre une suggestion à l'équipe.\n"
                "`/mon_parcours` — consulter son rang honorifique.",
            ),
            (
                "💬 Communauté et détente",
                "`/question_du_jour` — lancer une discussion.\n"
                "`/compliment [membre]` — partager un mot positif.\n"
                "`/blague [categorie]` — découvrir une blague.\n"
                "`/devinette` — résoudre une devinette.\n"
                "`/traduire texte langue` — traduire si le service est configuré.",
            ),
            (
                "🧠 Quiz culturel",
                "`/quiz_lancer [manches]` — lancer un quiz (1 à 10 manches, 12 joueurs maximum). "
                "Chaque bonne réponse rapporte un point.\n"
                "`/quiz_arreter` — arrêter le quiz et publier le classement. "
                "Commandes réservées à l'équipe.",
            ),
            (
                "🎫 Tickets et signalements",
                "Dans le salon de demande de ticket, clique sur **Créer un ticket** puis remplis le formulaire.\n"
                "`/ticket_ouvrir sujet details` — autre moyen d'ouvrir un ticket privé.\n"
                "`/ticket_fermer` — fermer le ticket depuis son salon.\n"
                "`/signaler motif [salon] [message_id]` — transmettre discrètement un signalement.",
            ),
            (
                "🎉 Événements et concours",
                "`/evenements` — consulter les prochains événements.\n"
                "`/evenement_creer titre date_heure description salon [lieu]` — publier un événement.\n"
                "`/evenement_fermer numero` — fermer les inscriptions.\n"
                "`/concours_creer prix duree_heures [gagnants] [salon]` — lancer un concours.\n"
                "`/concours_annuler numero` — annuler un concours (équipe).",
            ),
            (
                "🛡️ Équipe et modération",
                "`/annonce salon titre message [image]` · `/alerte_equipe message` · `/message_anonyme message`\n"
                "`/avertir` · `/avertissements` · `/retirer_avertissement`\n"
                "`/timeout` · `/untimeout` · `/expulser` · `/bannir` · `/debannir`\n"
                "`/purger` · `/note_membre` · `/actualiser_rangs`\n"
                "Ces commandes nécessitent les permissions ou le rôle d'équipe approprié.",
            ),
            (
                "🎂 Anniversaires",
                "`/anniversaire_definir jour mois` — enregistrer uniquement le jour et le mois.\n"
                "`/anniversaire_supprimer` — supprimer la date enregistrée.\n"
                "Les souhaits sont publiés automatiquement à 9 h, heure de Paris.",
            ),
        ]
        for name, value in sections:
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text="HORIZONS • Nos différences nous rapprochent")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profil", description="Afficher les informations publiques d'un membre.")
    async def profil(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        target = membre or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message("Ce profil n'est pas disponible ici.", ephemeral=True); return
        embed = horizons_embed(title=f"Profil de {target.display_name}", color=target.color if target.color.value else discord.Color.blurple())
        embed.set_author(name=f'Membre : {target.display_name}', icon_url=target.display_avatar.url)
        embed.add_field(name="Compte créé", value=discord.utils.format_dt(target.created_at, style="D"), inline=True)
        if target.joined_at: embed.add_field(name="A rejoint HORIZONS", value=discord.utils.format_dt(target.joined_at, style="D"), inline=True)
        visible_roles = [r.mention for r in reversed(target.roles[1:]) if not r.is_default()]
        embed.add_field(name="Rôles", value=", ".join(visible_roles[:15]) if visible_roles else "Aucun rôle affiché", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serveur", description="Afficher les informations du serveur.")
    async def serveur(self, interaction: discord.Interaction):
        g = interaction.guild
        if not g:
            await interaction.response.send_message("Cette commande est disponible sur le serveur.", ephemeral=True); return
        embed = horizons_embed(title=f"🌅 {g.name}", description=g.description or "Nos différences nous rapprochent.", color=discord.Color.blurple())
        embed.add_field(name="Membres", value=str(g.member_count or "—"))
        embed.add_field(name="Créé le", value=discord.utils.format_dt(g.created_at, style="D"))
        if g.icon: embed.set_image(url=g.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="proposer", description="Transmettre une idée à l'équipe HORIZONS.")
    @app_commands.describe(idee="Ton idée ou ta suggestion")
    async def proposer(self, interaction: discord.Interaction, idee: app_commands.Range[str, 10, 1500]):
        from config import SUGGESTION_CHANNEL_ID
        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID) if SUGGESTION_CHANNEL_ID else None
        if channel is None:
            await interaction.response.send_message("Le canal des propositions n'est pas encore configuré. Tu peux contacter l'équipe.", ephemeral=True); return
        embed = horizons_embed(title="💡 Nouvelle proposition", description=idee, color=discord.Color.teal())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now(LOCAL_TIMEZONE)
        await channel.send(embed=embed)
        await interaction.response.send_message("Merci ! Ta proposition a été transmise à l'équipe.", ephemeral=True)

    @app_commands.command(name="presentation", description="Recevoir un rappel pour se présenter.")
    async def presentation(self, interaction: discord.Interaction):
        from config import INTRO_CHANNEL_ID
        channel = self.bot.get_channel(INTRO_CHANNEL_ID) if INTRO_CHANNEL_ID else None
        mention = channel.mention if channel else "le salon de présentation"
        await interaction.response.send_message(f"Bienvenue dans HORIZONS ! Tu peux faire connaissance avec la communauté dans {mention}.", ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(General(bot))
