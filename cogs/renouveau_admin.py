"""Réorganisation HORIZONS : opérations explicites, réservées au fondateur.
Aucune mutation n'est exécutée au démarrage du bot.
"""
import discord
import unicodedata
from discord import app_commands
from discord.ext import commands

WELCOME_CATEGORY = 1566562020273168506
STAFF_CATEGORY = 1566562044604317848
TICKET_CATEGORY = 1567218409656156250
TICKET_REQUEST = 1567217890967425135
NEW_MEMBER_ROLE = 1566561929349304360
# Identifiants vérifiés sur l'export de structure du 17/11/2026.
OBSOLETE_CHANNELS = {
    1568958163875528754: "inspiration quotidienne",
    1567247269970059345: "missions horizons",
    1567247726985355424: "défis collectifs",
    1569434249784729634: "observatoire",
    1569434251785412699: "anomalies",
    1569434252909608980: "nox (salon de publications)",
    1569434254448918701: "chroniques",
}


# Catégories issues de l'export du 17 novembre 2026 ; contrôle supplémentaire
# pour éviter de supprimer un salon déplacé ou réaffecté depuis cet export.
EXPECTED_CATEGORIES = {
    1568958163875528754: 1566567464530088026,
    1567247269970059345: 1567247035688554596,
    1567247726985355424: 1567247035688554596,
    1569434249784729634: 1569434248652521605,
    1569434251785412699: 1569434248652521605,
    1569434252909608980: 1569434248652521605,
    1569434254448918701: 1569434248652521605,
}

def channel_is_expected(channel, label: str, channel_id: int, guild) -> tuple[bool, str]:
    if channel is None:
        return False, "salon absent"
    if not isinstance(channel, discord.TextChannel):
        return False, "type de salon différent"
    if channel.guild.id != guild.id:
        return False, "serveur différent"
    if channel.category_id != EXPECTED_CATEGORIES[channel_id]:
        return False, "catégorie modifiée depuis l'export"
    expected = normalized(label.split(" (")[0])
    if expected != normalized(channel.name):
        return False, "nom modifié depuis l'export"
    return True, "correspond à l'export"

def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if c.isalnum() and not unicodedata.combining(c))

class RenouveauAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def founder(interaction: discord.Interaction) -> bool:
        return bool(interaction.guild and interaction.user.id == interaction.guild.owner_id)

    renouveau = app_commands.Group(name="renouveau", description="Réorganisation contrôlée de HORIZONS")

    @renouveau.command(name="audit", description="Lister les salons obsolètes sans les supprimer")
    async def audit(self, interaction: discord.Interaction):
        if not self.founder(interaction):
            return await interaction.response.send_message("Réservé au propriétaire du serveur.", ephemeral=True)
        guild = interaction.guild
        lines = []
        for cid, label in OBSOLETE_CHANNELS.items():
            channel = guild.get_channel(cid)
            ok, reason = channel_is_expected(channel, label, cid, guild)
            lines.append(f"• {channel.mention if channel else 'Absent'} — {label} (`{cid}`) — {'éligible' if ok else 'REFUSÉ'} : {reason}")
        await interaction.response.send_message("**Salons proposés à la suppression (aucune action)**\n" + "\n".join(lines), ephemeral=True)

    @renouveau.command(name="tickets", description="Déplacer les tickets et ouvrir la demande aux nouveaux membres")
    @app_commands.describe(confirmation="Écrire DEPLACER pour appliquer la réorganisation")
    async def tickets(self, interaction: discord.Interaction, confirmation: str):
        if not self.founder(interaction):
            return await interaction.response.send_message("Réservé au propriétaire du serveur.", ephemeral=True)
        if confirmation != "DEPLACER":
            return await interaction.response.send_message("Aucun changement. Pour confirmer, écris `DEPLACER`.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if not interaction.app_permissions.manage_channels or not interaction.app_permissions.manage_roles:
            return await interaction.followup.send("Opération annulée : permissions Gérer les salons et Gérer les rôles nécessaires.", ephemeral=True)
        g = interaction.guild
        accueil, staff, cat, demande = (g.get_channel(i) for i in (WELCOME_CATEGORY, STAFF_CATEGORY, TICKET_CATEGORY, TICKET_REQUEST))
        role = g.get_role(NEW_MEMBER_ROLE)
        if not isinstance(accueil, discord.CategoryChannel) or not isinstance(staff, discord.CategoryChannel) or not isinstance(cat, discord.CategoryChannel) or not isinstance(demande, discord.TextChannel) or role is None:
            return await interaction.followup.send("Opération annulée : une catégorie, le salon ou le rôle Nouveau membre est introuvable.", ephemeral=True)
        # Refuser de modifier des objets réaffectés depuis l'export.
        if normalized(demande.name) != normalized("demande de ticket"):
            return await interaction.followup.send("Opération annulée : le salon de demande de ticket a été renommé.", ephemeral=True)
        if normalized(cat.name) != normalized("support et tickets"):
            return await interaction.followup.send("Opération annulée : la catégorie Support & Tickets a été renommée.", ephemeral=True)
        try:
            await demande.edit(category=accueil, sync_permissions=False, reason="Renouveau HORIZONS : accès support dès l'arrivée")
            await demande.set_permissions(role, view_channel=True, read_message_history=True, reason="Accès des nouveaux membres aux demandes de tickets")
            await cat.move(after=staff, reason="Renouveau HORIZONS : catégorie tickets après espace staff")
        except discord.Forbidden:
            return await interaction.followup.send("Permissions Discord insuffisantes : vérifier Gérer les salons et les rôles du bot.", ephemeral=True)
        except discord.HTTPException as exc:
            return await interaction.followup.send(f"Réorganisation partielle ou impossible : {exc}. Vérifie la structure avant de relancer.", ephemeral=True)
        await interaction.followup.send("Demande de ticket déplacée dans Accueil, accès Nouveau membre autorisé ; catégorie Support & Tickets placée après Espace Staff. Vérifie également les permissions des autres rôles.", ephemeral=True)

    @renouveau.command(name="supprimer_salons", description="Supprimer uniquement les sept salons obsolètes identifiés")
    @app_commands.describe(confirmation="Écrire exactement SUPPRIMER-7-SALONS pour confirmer")
    async def supprimer_salons(self, interaction: discord.Interaction, confirmation: str):
        if not self.founder(interaction):
            return await interaction.response.send_message("Réservé au propriétaire du serveur.", ephemeral=True)
        if confirmation != "SUPPRIMER-7-SALONS":
            return await interaction.response.send_message("Aucune suppression. Consulte d'abord `/renouveau audit`, puis confirme avec `SUPPRIMER-7-SALONS`.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if not interaction.app_permissions.manage_channels:
            return await interaction.followup.send("Opération annulée : permission Gérer les salons nécessaire.", ephemeral=True)
        deleted, failed = [], []
        for cid, label in OBSOLETE_CHANNELS.items():
            channel = interaction.guild.get_channel(cid)
            if channel is None:
                continue
            eligible, reason = channel_is_expected(channel, label, cid, interaction.guild)
            if not eligible:
                failed.append(f"{label}: {reason}, suppression refusée")
                continue
            try:
                await channel.delete(reason=f"Renouveau HORIZONS demandé par le propriétaire : {label}")
                deleted.append(label)
            except discord.HTTPException as exc:
                failed.append(f"{label}: {exc}")
        await interaction.followup.send(f"Salons supprimés : {', '.join(deleted) or 'aucun'}." + (f"\nÉchecs : {'; '.join(failed)}" if failed else "") + "\nAttention : suppression définitive des messages de ces salons.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RenouveauAdmin(bot))
