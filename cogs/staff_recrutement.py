"""Candidatures staff HORIZONS : consentement, validation fondateur, rôles.

Le panneau est publié uniquement sur commande afin d'éviter les doublons.
"""
from __future__ import annotations

import os
import logging
import sqlite3
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

WAITING = int(os.getenv('STAFF_PENDING_ROLE_ID', '1571536139498688653'))
TEAM = int(os.getenv('STAFF_ROLE_ID', '1566561923670212828'))
FOUNDER = int(os.getenv('FOUNDER_ROLE_ID', '1566561887305339001'))
RULES = int(os.getenv('STAFF_RULES_CHANNEL_ID', '1571534451144392744'))
LOGS = int(os.getenv('FOUNDER_LOGS_CHANNEL_ID', '1571537581596876941'))
FUNCTIONS = {
    'animateur': ('Animateur', int(os.getenv('STAFF_ANIMATEUR_ROLE_ID', '1566561919647875152'))),
    'mediateur': ('Médiateur', int(os.getenv('STAFF_MEDIATEUR_ROLE_ID', '1566561912794124338'))),
    'moderateur': ('Modérateur', int(os.getenv('STAFF_MODERATEUR_ROLE_ID', '1566561900865785918'))),
    'administrateur': ('Administrateur', int(os.getenv('STAFF_ADMIN_ROLE_ID', '1566561889188839477'))),
}
DB = Path(__file__).resolve().parent.parent / 'data' / 'staff_recrutement.sqlite3'
LOG = logging.getLogger(__name__)


def founder(i: discord.Interaction) -> bool:
    return bool(i.guild and isinstance(i.user, discord.Member) and (
        i.guild.owner_id == i.user.id or any(r.id == FOUNDER for r in i.user.roles)))


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS applications (guild_id INTEGER NOT NULL, member_id INTEGER NOT NULL, status TEXT NOT NULL, function TEXT, reviewer_id INTEGER, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(guild_id, member_id))')
    columns = {row[1] for row in db.execute('PRAGMA table_info(applications)')}
    if 'decision_message_id' not in columns:
        db.execute('ALTER TABLE applications ADD COLUMN decision_message_id INTEGER')
    db.commit()
    return db


class Acceptance(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="J'accepte le règlement Staff", emoji='📜', style=discord.ButtonStyle.success, custom_id='horizons:staff:accept:v1')
    async def accept(self, i: discord.Interaction, button: discord.ui.Button):
        if not i.guild or not isinstance(i.user, discord.Member):
            return await i.response.send_message('Action réservée au serveur.', ephemeral=True)
        if not any(r.id == WAITING for r in i.user.roles):
            return await i.response.send_message('Le rôle Staff en attente est nécessaire.', ephemeral=True)
        log = i.guild.get_channel(LOGS)
        if not isinstance(log, discord.TextChannel):
            return await i.response.send_message('Salon des validations indisponible. Préviens le Fondateur.', ephemeral=True)
        with connection() as db:
            row = db.execute('SELECT status FROM applications WHERE guild_id=? AND member_id=?', (i.guild_id, i.user.id)).fetchone()
            if row and row[0] in ('pending', 'processing', 'approved'):
                return await i.response.send_message('Ta demande est déjà enregistrée.', ephemeral=True)
            db.execute('INSERT INTO applications(guild_id,member_id,status,function,reviewer_id) VALUES(?,?,\'pending\',NULL,NULL) ON CONFLICT(guild_id,member_id) DO UPDATE SET status=\'pending\',function=NULL,reviewer_id=NULL,updated_at=CURRENT_TIMESTAMP', (i.guild_id, i.user.id))
        embed = discord.Embed(title='👑 Candidature Staff à valider', description=f'{i.user.mention} a accepté le règlement Staff.\nChoisis une fonction ou refuse la demande.', color=0xC9A44C)
        embed.set_footer(text=f'HORIZONS • Candidat : {i.user.id}')
        try:
            posted = await log.send(embed=embed, view=Decision(i.user.id), allowed_mentions=discord.AllowedMentions(users=[i.user], roles=False, everyone=False))
            with connection() as db:
                db.execute("UPDATE applications SET decision_message_id=? WHERE guild_id=? AND member_id=? AND status='pending'", (posted.id, i.guild_id, i.user.id))
        except discord.HTTPException:
            with connection() as db:
                db.execute('DELETE FROM applications WHERE guild_id=? AND member_id=? AND status=\'pending\'', (i.guild_id, i.user.id))
            return await i.response.send_message('Impossible de transmettre la demande. Réessaie plus tard.', ephemeral=True)
        await i.response.send_message('Ton acceptation a été transmise au Fondateur. Merci !', ephemeral=True)


class DecisionSelect(discord.ui.Select):
    def __init__(self, member_id: int):
        self.member_id = member_id
        opts = [discord.SelectOption(label=name, value=key) for key, (name, _) in FUNCTIONS.items()]
        opts.append(discord.SelectOption(label='Refuser la candidature', value='refuse', emoji='❌'))
        super().__init__(placeholder='Décision du Fondateur', options=opts, custom_id=f'horizons:staff:decision:{member_id}')

    async def callback(self, i: discord.Interaction):
        if not founder(i):
            return await i.response.send_message('Réservé au Fondateur.', ephemeral=True)
        choice = self.values[0]
        if not i.guild:
            return await i.response.send_message('Serveur indisponible.', ephemeral=True)
        await i.response.defer(ephemeral=True, thinking=True)
        with connection() as db:
            updated = db.execute("UPDATE applications SET status='processing', reviewer_id=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND member_id=? AND status='pending'", (i.user.id, i.guild_id, self.member_id)).rowcount
        if not updated:
            return await i.followup.send('Cette demande a déjà été traitée ou est en cours.', ephemeral=True)
        try:
            # Le refus doit rester possible même si le candidat a quitté le serveur.
            # Une approbation exige, en revanche, que le membre soit toujours présent.
            if choice == 'refuse':
                outcome = 'refused'
                summary = 'Candidature refusée.'
            else:
                member = i.guild.get_member(self.member_id) or await i.guild.fetch_member(self.member_id)
                label, rid = FUNCTIONS[choice]
                team = i.guild.get_role(TEAM)
                role = i.guild.get_role(rid)
                if not team or not role:
                    raise RuntimeError('Rôle Staff introuvable')
                me = i.guild.me
                if me is None or not me.guild_permissions.manage_roles:
                    raise RuntimeError('Permission Gérer les rôles manquante')
                pending = i.guild.get_role(WAITING)
                if team >= me.top_role or role >= me.top_role or (pending and pending in member.roles and pending >= me.top_role):
                    raise RuntimeError('Le rôle du bot doit être au-dessus des rôles Staff à modifier')
                # En cas d'échec du retrait du rôle d'attente, éviter de laisser
                # une candidature en attente avec des droits Staff déjà accordés.
                newly_added = [r for r in (team, role) if r not in member.roles]
                await member.add_roles(team, role, reason=f'Validation staff par {i.user}')
                try:
                    if pending and pending in member.roles:
                        await member.remove_roles(pending, reason='Candidature staff validée')
                except discord.HTTPException:
                    if newly_added:
                        try:
                            await member.remove_roles(*newly_added, reason='Annulation validation Staff incomplète')
                        except discord.HTTPException:
                            LOG.exception('Annulation partielle impossible pour candidature %s', self.member_id)
                    raise
                outcome = 'approved'
                summary = f'Candidature validée : {label} + Équipe STAFF.'
            with connection() as db:
                db.execute('UPDATE applications SET status=?,function=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND member_id=?', (outcome, choice, i.guild_id, self.member_id))
        except (discord.HTTPException, RuntimeError) as exc:
            with connection() as db:
                db.execute("UPDATE applications SET status='pending',updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND member_id=? AND status='processing'", (i.guild_id, self.member_id))
            await i.followup.send(f'Validation non terminée : {exc}. Vérifie les permissions et réessaie.', ephemeral=True)
            return
        # La décision et les rôles sont déjà enregistrés : un échec d'édition du
        # message de logs ne doit surtout pas remettre la candidature en attente.
        if i.message:
            try:
                await i.message.edit(view=None)
            except discord.HTTPException:
                LOG.exception('Impossible de désactiver le menu de candidature %s déjà traitée', self.member_id)
        await i.followup.send(summary, ephemeral=True)


class Decision(discord.ui.View):
    def __init__(self, member_id: int):
        super().__init__(timeout=None)
        self.add_item(DecisionSelect(member_id))


class StaffRecrutement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Un arrêt pendant une validation peut laisser une candidature 'processing'.
        # La rétablir en attente permet au Fondateur de reprendre la décision.
        with connection() as db:
            db.execute("UPDATE applications SET status='pending',updated_at=CURRENT_TIMESTAMP WHERE status='processing'")
            pending = db.execute("SELECT member_id,decision_message_id FROM applications WHERE status='pending'").fetchall()
        self.bot.add_view(Acceptance())
        for member_id, message_id in pending:
            # Associer chaque vue à son message empêche les candidatures
            # simultanées de se substituer leurs menus après redémarrage.
            if message_id:
                self.bot.add_view(Decision(member_id), message_id=message_id)
            else:
                # Ne pas restaurer une vue sans message : l'ancien panneau peut
                # être absent et une interaction ne doit pas cibler un autre dossier.
                LOG.warning('Candidature %s sans message de validation ; republication manuelle nécessaire', member_id)

    @app_commands.command(name='reglement_staff', description='Publier ou actualiser le panneau du règlement Staff (Fondateur)')
    async def reglement_staff(self, i: discord.Interaction):
        if not founder(i):
            return await i.response.send_message('Réservé au Fondateur.', ephemeral=True)
        channel = i.guild.get_channel(RULES)
        if not isinstance(channel, discord.TextChannel):
            return await i.response.send_message('Salon Règlement Staff introuvable.', ephemeral=True)
        embed = discord.Embed(title='🛡️ Règlement de l’équipe HORIZONS', description=(
            '**Respect et exemplarité** — Accueillir chaque personne sans discrimination.\n\n'
            '**Confidentialité** — Ne jamais divulguer les échanges internes, tickets ou informations privées.\n\n'
            '**Neutralité et discernement** — Agir avec impartialité, sans abus de pouvoir.\n\n'
            '**Esprit d’équipe** — Communiquer avec les autres membres du staff et respecter les décisions collectives.\n\n'
            '**Disponibilité responsable** — Prévenir en cas d’absence ; ne pas intervenir au-delà de ses moyens.\n\n'
            'En cliquant sur le bouton, tu confirmes avoir lu et accepté ces engagements. '
            '**L’acceptation ne donne pas automatiquement accès au Staff : le Fondateur doit valider ta candidature.**'
        ), color=0xC9A44C)
        embed.set_footer(text='HORIZONS • Unis dans la diversité')
        await i.response.defer(ephemeral=True)
        async for msg in channel.history(limit=100):
            if msg.author.id == self.bot.user.id and msg.embeds and msg.embeds[0].title == embed.title:
                await msg.edit(embed=embed, view=Acceptance())
                return await i.followup.send('Panneau Staff actualisé.', ephemeral=True)
        await channel.send(embed=embed, view=Acceptance())
        await i.followup.send('Panneau Staff publié.', ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffRecrutement(bot))
