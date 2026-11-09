"""Workflow de proposition de Cercles, validé par le staff, persistant en SQLite."""
from __future__ import annotations
import logging
import sqlite3
import discord
from discord.ext import commands
from config import CIRCLE_PROPOSALS_CHANNEL_ID, CIRCLES_CHANNEL_ID, ADMIN_BOT_LOG_CHANNEL_ID
from .storage import db
from .embed_theme import horizons_embed, GOLD, get_logo_url

log = logging.getLogger(__name__)


def proposal_embed(row, *, staff=False):
    e = horizons_embed(title=f"🌙 Proposition de Cercle #{row['id']} — {row['name']}",
        description=f"**Thème :** {row['theme']}\n**Objectif :** {row['goal']}\n**Activités :** {row['activities']}\n**Rythme :** {row['rhythm']}")
    e.add_field(name="Proposé par", value=f"<@{row['user_id']}>", inline=True)
    e.add_field(name="Statut", value=row['status'], inline=True)
    if row['decision_note']:
        e.add_field(name="Réponse du staff", value=row['decision_note'], inline=False)
    e.set_footer(text="HORIZONS • Proposition soumise à validation" if staff else "HORIZONS • Cercle communautaire")
    return e


def staff_allowed(member):
    return isinstance(member, discord.Member) and (member.guild_permissions.administrator or member.guild_permissions.manage_guild)


class CircleProposalModal(discord.ui.Modal, title="Proposer un Cercle HORIZONS"):
    name = discord.ui.TextInput(label="Nom du Cercle", max_length=70)
    theme = discord.ui.TextInput(label="Thème", max_length=120)
    goal = discord.ui.TextInput(label="Objectif du Cercle", style=discord.TextStyle.paragraph, max_length=600)
    activities = discord.ui.TextInput(label="Activités envisagées", style=discord.TextStyle.paragraph, max_length=500)
    rhythm = discord.ui.TextInput(label="Rythme et envie de l'animer", max_length=180)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or interaction.channel_id != CIRCLE_PROPOSALS_CHANNEL_ID:
            await interaction.response.send_message("Utilise le panneau du salon Proposer un Cercle.", ephemeral=True)
            return
        guild = interaction.guild
        staff_channel = guild.get_channel(ADMIN_BOT_LOG_CHANNEL_ID)
        if not isinstance(staff_channel, discord.TextChannel) or not staff_channel.permissions_for(guild.me).send_messages:
            await interaction.response.send_message("Le circuit de validation est temporairement indisponible. Réessaie plus tard.", ephemeral=True)
            return
        # Refuser une publication dans un salon public ou accessible à @everyone.
        if staff_channel.permissions_for(guild.default_role).view_channel:
            await interaction.response.send_message("Le salon de validation n'est pas privé : le staff doit corriger ses permissions.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        with db() as conn:
            existing = conn.execute("SELECT id FROM circle_proposals WHERE guild_id=? AND user_id=? AND status='pending' LIMIT 1", (guild.id, interaction.user.id)).fetchone()
            if existing:
                await interaction.followup.send(f"Tu as déjà une proposition en attente (#{existing['id']}).", ephemeral=True)
                return
            cursor = conn.execute("INSERT INTO circle_proposals (guild_id,user_id,name,theme,goal,activities,rhythm,status) VALUES (?,?,?,?,?,?,?,'pending')",
                (guild.id,interaction.user.id,str(self.name),str(self.theme),str(self.goal),str(self.activities),str(self.rhythm)))
            pid = cursor.lastrowid
            row = conn.execute("SELECT * FROM circle_proposals WHERE id=?",(pid,)).fetchone()
        try:
            msg = await staff_channel.send(embed=proposal_embed(row,staff=True), view=CircleStaffView(pid), allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden,discord.HTTPException):
            with db() as conn:
                conn.execute("UPDATE circle_proposals SET status='delivery_failed' WHERE id=? AND status='pending'",(pid,))
            await interaction.followup.send("Impossible de transmettre la proposition au staff. Aucun Cercle n'a été publié.", ephemeral=True)
            return
        with db() as conn:
            conn.execute("UPDATE circle_proposals SET staff_message_id=? WHERE id=?",(msg.id,pid))
        await interaction.followup.send(f"Ta proposition #{pid} a été transmise à l'équipe. Tu recevras une réponse après examen. 💙", ephemeral=True)


class CircleProposalEntry(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Proposer un Cercle", emoji="🌙", style=discord.ButtonStyle.primary, custom_id="horizons:circles:propose")
    async def propose(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CircleProposalModal())


class CircleDecisionModal(discord.ui.Modal):
    reason = discord.ui.TextInput(label="Motif ou précisions", style=discord.TextStyle.paragraph, max_length=600, required=False)

    def __init__(self, pid: int, action: str):
        super().__init__(title="Décision pour le Cercle")
        self.pid, self.action = pid, action

    async def on_submit(self, interaction: discord.Interaction):
        await decide_circle(interaction, self.pid, self.action, str(self.reason).strip())


async def decide_circle(interaction: discord.Interaction, pid: int, action: str, note: str):
    if not staff_allowed(interaction.user):
        await interaction.response.send_message("Réservé à l'administration du serveur.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    with db() as conn:
        row = conn.execute("SELECT * FROM circle_proposals WHERE id=? AND guild_id=?",(pid,interaction.guild_id)).fetchone()
        if not row or row['status'] != 'pending':
            await interaction.followup.send("Cette proposition a déjà été traitée ou est introuvable.",ephemeral=True)
            return
    if action == 'approve':
        dest = interaction.guild.get_channel(CIRCLES_CHANNEL_ID)
        if not isinstance(dest, discord.TextChannel):
            await interaction.followup.send("Salon Cercles introuvable : validation annulée.",ephemeral=True)
            return
        # État transitoire atomique pour empêcher deux validations simultanées.
        with db() as conn:
            result = conn.execute("UPDATE circle_proposals SET status='publishing' WHERE id=? AND status='pending'",(pid,))
            if result.rowcount != 1:
                await interaction.followup.send("Cette proposition est déjà en cours de traitement.",ephemeral=True)
                return
        try:
            e = horizons_embed(title=f"🌐 Nouveau Cercle HORIZONS — {row['name']}",
                description=f"**Thème :** {row['theme']}\n**Objectif :** {row['goal']}\n**Activités proposées :** {row['activities']}\n**Rythme :** {row['rhythm']}\n\n**À l'origine du Cercle :** <@{row['user_id']}>")
            if not e.thumbnail.url:
                e.set_thumbnail(url=interaction.client.user.display_avatar.url)
            published = await dest.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden,discord.HTTPException):
            with db() as conn:
                conn.execute("UPDATE circle_proposals SET status='pending' WHERE id=? AND status='publishing'",(pid,))
            await interaction.followup.send("Publication impossible, la proposition reste en attente.",ephemeral=True)
            return
        status = 'approved'
        with db() as conn:
            conn.execute("UPDATE circle_proposals SET status=?, published_message_id=?, decision_note=?, reviewer_id=? WHERE id=?",(status,published.id,note,interaction.user.id,pid))
    else:
        status = 'rejected' if action == 'reject' else 'needs_info'
        with db() as conn:
            result=conn.execute("UPDATE circle_proposals SET status=?, decision_note=?, reviewer_id=? WHERE id=? AND status='pending'",(status,note,interaction.user.id,pid))
            if result.rowcount != 1:
                await interaction.followup.send("Déjà traité.",ephemeral=True)
                return
    with db() as conn:
        updated=conn.execute("SELECT * FROM circle_proposals WHERE id=?",(pid,)).fetchone()
    try:
        if interaction.message:
            await interaction.message.edit(embed=proposal_embed(updated,staff=True),view=None)
    except (discord.Forbidden,discord.HTTPException):
        log.warning("Impossible d'actualiser le panneau staff du Cercle %s",pid)
    labels={'approved':f"acceptée et publiée dans <#{CIRCLES_CHANNEL_ID}>",'rejected':'refusée','needs_info':'en attente de précisions'}
    notice=f"Ta proposition de Cercle **{row['name']}** a été {labels[status]}."
    if note: notice+=f"\n**Message du staff :** {note}"
    try:
        user=await interaction.client.fetch_user(row['user_id'])
        await user.send(notice,allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden,discord.HTTPException):
        log.info("DM impossible pour la proposition Cercle %s",pid)
    await interaction.followup.send(f"Proposition #{pid} : {status}.",ephemeral=True)


class CircleStaffView(discord.ui.View):
    def __init__(self, pid: int):
        super().__init__(timeout=None)
        self.pid=pid
        for label,emoji,style,action in [
            ('Approuver','✅',discord.ButtonStyle.success,'approve'),
            ('Refuser','❌',discord.ButtonStyle.danger,'reject'),
            ('Demander des précisions','📝',discord.ButtonStyle.secondary,'info')]:
            b=discord.ui.Button(label=label,emoji=emoji,style=style,custom_id=f'horizons:circles:{action}:{pid}')
            async def callback(interaction, action=action):
                if not staff_allowed(interaction.user):
                    await interaction.response.send_message("Réservé à l'administration.",ephemeral=True)
                else:
                    await interaction.response.send_modal(CircleDecisionModal(self.pid,action))
            b.callback=callback
            self.add_item(b)


class CircleProposals(commands.Cog):
    def __init__(self, bot): self.bot=bot

    async def cog_load(self):
        with db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS circle_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                name TEXT NOT NULL, theme TEXT NOT NULL, goal TEXT NOT NULL, activities TEXT NOT NULL,
                rhythm TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                staff_message_id INTEGER, published_message_id INTEGER, reviewer_id INTEGER,
                decision_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            rows=conn.execute("SELECT id,staff_message_id FROM circle_proposals WHERE status='pending' AND staff_message_id IS NOT NULL").fetchall()
        self.bot.add_view(CircleProposalEntry())
        for row in rows:
            self.bot.add_view(CircleStaffView(row['id']),message_id=row['staff_message_id'])


async def setup(bot):
    await bot.add_cog(CircleProposals(bot))
