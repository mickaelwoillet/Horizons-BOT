"""Boîte à idées, mur de la solidarité et tableau de bord staff HORIZONS."""
from __future__ import annotations
import logging as _sky_logging
from .sky_map import grant as grant_sky_star
_sky_log = _sky_logging.getLogger(__name__)
from cogs.embed_theme import get_logo_url, horizons_embed, wait_for_logo_ready

from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, STAFF_ROLE_ID, IDEAS_CHANNEL_ID, SOLIDARITY_CHANNEL_ID
from .storage import db


def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or any(role.id == STAFF_ROLE_ID for role in member.roles)


def idea_embed(idea_id: int, content: str, status: str = "received") -> discord.Embed:
    labels = {"received": "📥 Reçue", "review": "🔎 En réflexion", "accepted": "✅ Acceptée", "rejected": "❌ Non retenue", "done": "🎉 Réalisée"}
    embed = horizons_embed(title=f"💡 Idée de la communauté • #{idea_id}", description=content, color=discord.Color.gold())
    embed.add_field(name="État", value=labels.get(status, "📥 Reçue"), inline=True)
    embed.set_footer(text="HORIZONS • Proposition publiée anonymement")
    return embed


class IdeaVoteView(discord.ui.View):
    def __init__(self, idea_id: int):
        super().__init__(timeout=None)
        self.idea_id = idea_id
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.custom_id = f"horizons:idea:{idea_id}:{child.custom_id.split(':')[-1]}"

    async def update_vote(self, interaction: discord.Interaction, vote: int):
        with db() as conn:
            conn.execute("INSERT INTO community_idea_votes(idea_id,user_id,vote) VALUES(?,?,?) ON CONFLICT(idea_id,user_id) DO UPDATE SET vote=excluded.vote", (self.idea_id, interaction.user.id, vote))
            counts = conn.execute("SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END), SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM community_idea_votes WHERE idea_id=?", (self.idea_id,)).fetchone()
        await interaction.response.send_message(f"Ton vote est enregistré. 👍 {counts[0] or 0} • 👎 {counts[1] or 0}", ephemeral=True)

    @discord.ui.button(label="Utile", emoji="👍", style=discord.ButtonStyle.success, custom_id="idea:up")
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_vote(interaction, 1)

    @discord.ui.button(label="À retravailler", emoji="👎", style=discord.ButtonStyle.secondary, custom_id="idea:down")
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_vote(interaction, -1)


class DashboardView(discord.ui.View):
    def __init__(self, cog: "CommunityHub"):
        super().__init__(timeout=180)
        self.cog = cog

    @discord.ui.select(placeholder="Choisir une rubrique du tableau de bord", min_values=1, max_values=1, options=[
        discord.SelectOption(label="Vue générale", value="overview", emoji="📊"),
        discord.SelectOption(label="Boîte à idées", value="ideas", emoji="💡"),
        discord.SelectOption(label="Solidarité", value="solidarity", emoji="💜"),
        discord.SelectOption(label="Modération", value="moderation", emoji="🛡️"),
        discord.SelectOption(label="Tickets", value="tickets", emoji="🎫"),
        discord.SelectOption(label="Événements", value="events", emoji="📅"),
    ])
    async def select_section(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("Accès réservé au staff autorisé.", ephemeral=True); return
        embed = self.cog.dashboard_embed(interaction.guild, select.values[0])
        await interaction.response.edit_message(embed=embed, view=self)


class IdeaModal(discord.ui.Modal, title="Proposer une idée HORIZONS"):
    proposition = discord.ui.TextInput(label="Ton idée", style=discord.TextStyle.paragraph, min_length=10, max_length=1500)
    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("CommunityHub")
        if cog: await cog.idee.callback(cog, interaction, str(self.proposition.value))
        else: await interaction.response.send_message("Service indisponible.", ephemeral=True)


class IdeaPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Proposer une idée", emoji="💡", style=discord.ButtonStyle.primary, custom_id="horizons:ideas:propose:v2")
    async def propose(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IdeaModal())
    @discord.ui.button(label="Mes idées", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="horizons:ideas:mine:v2")
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("CommunityHub")
        if cog: await cog.mes_idees.callback(cog, interaction)
        else: await interaction.response.send_message("Service indisponible.", ephemeral=True)


class ThanksModal(discord.ui.Modal, title="Un éclat de reconnaissance"):
    def __init__(self, member: discord.Member):
        super().__init__(); self.member = member
    motif = discord.ui.TextInput(label="Motif", placeholder="Écoute, entraide, gentillesse...", min_length=3, max_length=60)
    message = discord.ui.TextInput(label="Ton message", style=discord.TextStyle.paragraph, min_length=5, max_length=700)
    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("CommunityHub")
        if cog:
            reason = app_commands.Choice(name=str(self.motif.value), value=str(self.motif.value))
            await cog.remercier.callback(cog, interaction, self.member, reason, str(self.message.value))
        else: await interaction.response.send_message("Service indisponible.", ephemeral=True)


class ThanksSelect(discord.ui.UserSelect):
    def __init__(self): super().__init__(placeholder="Choisir la personne à remercier", min_values=1, max_values=1)
    async def callback(self, interaction: discord.Interaction):
        member = self.values[0]
        if not isinstance(member, discord.Member) and interaction.guild:
            member = interaction.guild.get_member(member.id)
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Membre introuvable.", ephemeral=True); return
        await interaction.response.send_modal(ThanksModal(member))


class ThanksSelectView(discord.ui.View):
    def __init__(self): super().__init__(timeout=180); self.add_item(ThanksSelect())


class ThanksPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Remercier quelqu'un", emoji="💜", style=discord.ButtonStyle.primary, custom_id="horizons:thanks:propose:v2")
    async def propose(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Qui souhaites-tu remercier ?", view=ThanksSelectView(), ephemeral=True)


class CommunityHub(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._explanations_checked = False
        self.bot.add_view(IdeaPanel())
        self.bot.add_view(ThanksPanel())

    @commands.Cog.listener()
    async def on_ready(self):
        await wait_for_logo_ready()
        if self._explanations_checked:
            return
        self._explanations_checked = True
        await self.ensure_explanation(IDEAS_CHANNEL_ID, "ideas_explanation_message", self.ideas_explanation(), view=IdeaPanel())
        await self.ensure_explanation(SOLIDARITY_CHANNEL_ID, "solidarity_explanation_message", self.solidarity_explanation(), view=ThanksPanel())
        with db() as conn:
            ids = [row[0] for row in conn.execute("SELECT id FROM community_ideas WHERE status IN ('received','review','accepted') AND message_id IS NOT NULL")]
        for idea_id in ids:
            self.bot.add_view(IdeaVoteView(idea_id))

    async def ensure_explanation(self, channel_id: int, key: str, embed: discord.Embed, view: discord.ui.View | None = None):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try: channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException: return
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            return
        with db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        if row:
            try:
                if isinstance(channel, discord.ForumChannel):
                    thread = await self.bot.fetch_channel(int(row["value"]))
                    if isinstance(thread, discord.Thread):
                        starter = await thread.fetch_message(thread.id)
                        await starter.edit(embed=embed, view=view)
                        return
                else:
                    message = await channel.fetch_message(int(row["value"]))
                    await message.edit(embed=embed, view=view)
                    return
            except (discord.NotFound, discord.HTTPException):
                pass
        try:
            if isinstance(channel, discord.ForumChannel):
                title = "✦ Fonctionnement de la boîte à idées" if key.startswith("ideas") else "✦ Fonctionnement du mur de la solidarité"
                created = await channel.create_thread(name=title, embeds=[embed], view=view)
                stored_id = created.thread.id
            else:
                message = await channel.send(embed=embed, view=view)
                stored_id = message.id
        except discord.HTTPException:
            return
        with db() as conn:
            conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(stored_id)))

    @staticmethod
    def ideas_explanation():
        e = horizons_embed(title="✦ La boîte à idées HORIZONS", description=(
            "**Une idée, une envie d'amélioration ? Elle a sa place ici !**\n\n"
            "Clique sur **Proposer une idée** pour proposer une amélioration, une activité ou une nouvelle fonctionnalité. "
            "Ta proposition sera publiée sans afficher ton nom aux membres.\n\n"
            "👍 Les membres peuvent voter pour les idées qu'ils trouvent utiles.\n"
            "🔎 L'équipe peut indiquer si une idée est en réflexion, acceptée, réalisée ou non retenue.\n\n"
            "Tu peux retrouver tes propositions avec **Mes idées**.\n\n"
            "**Quelques règles :** reste respectueux, explique ton idée clairement et ne publie aucune donnée personnelle. "
            "L'anonymat est public : l'équipe conserve une trace interne de l'auteur pour prévenir les abus."
        ), color=discord.Color.gold())
        e.set_footer(text="HORIZONS • Chaque idée peut ouvrir un nouvel horizon")
        return e

    @staticmethod
    def solidarity_explanation():
        e = horizons_embed(title="💜 Les Éclats de Reconnaissance · Mur de la solidarité", description=(
            "**Un merci peut illuminer la journée de quelqu'un.**\n\n"
            "Clique sur **Remercier quelqu’un** pour mettre en valeur un membre qui t'a aidé, écouté, encouragé ou simplement fait sourire.\n\n"
            "Choisis un motif et ajoute quelques mots sincères. Ton message sera publié ici avec ton nom : "
            "la reconnaissance est publique et positive.\n\n"
            "🤝 Écoute et soutien\n🌟 Gentillesse et bienveillance\n🧩 Entraide et disponibilité\n😊 Bonne humeur et encouragements\n\n"
            "Les messages doivent rester respectueux. Pas de classement de popularité, pas de compétition et aucune obligation de participer."
        ), color=discord.Color.gold())
        e.set_footer(text="HORIZONS • Les petits gestes créent de grands liens")
        return e

    @app_commands.command(name="idee", description="Déposer anonymement une idée pour HORIZONS.")
    @app_commands.describe(proposition="Décris ton idée en quelques phrases")
    async def idee(self, interaction: discord.Interaction, proposition: app_commands.Range[str, 10, 1500]):
        if interaction.guild_id != GUILD_ID:
            await interaction.response.send_message("Cette commande est réservée à HORIZONS.", ephemeral=True); return
        channel = self.bot.get_channel(IDEAS_CHANNEL_ID)
        if channel is None:
            try: channel = await self.bot.fetch_channel(IDEAS_CHANNEL_ID)
            except discord.HTTPException: channel = None
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.response.send_message("Le salon forum de la boîte à idées est introuvable. Préviens le staff.", ephemeral=True); return
        with db() as conn:
            cur = conn.execute("INSERT INTO community_ideas(guild_id,user_id,content,created_at) VALUES(?,?,?,?)", (interaction.guild_id, interaction.user.id, proposition, datetime.now(timezone.utc).isoformat()))
            idea_id = cur.lastrowid
        embed = idea_embed(idea_id, proposition)
        thread_id = None
        if isinstance(channel, discord.ForumChannel):
            created = await channel.create_thread(name=f"Idée #{idea_id} • proposition communautaire", embed=embed, view=IdeaVoteView(idea_id), allowed_mentions=discord.AllowedMentions.none())
            msg = created.message
            thread_id = created.thread.id
        else:
            msg = await channel.send(embed=embed, view=IdeaVoteView(idea_id), allowed_mentions=discord.AllowedMentions.none())
        with db() as conn:
            conn.execute("UPDATE community_ideas SET message_id=? WHERE id=?", (msg.id, idea_id))
            if thread_id is not None:
                conn.execute("UPDATE community_ideas SET thread_id=? WHERE id=?", (thread_id, idea_id))
        staff_channel = self.bot.get_channel(__import__('config').ALERT_LOG_CHANNEL_ID)
        if isinstance(staff_channel, discord.TextChannel):
            audit = horizons_embed(title=f"Journal interne — idée #{idea_id}", description=f"Auteur : {interaction.user} (`{interaction.user.id}`)\nMessage : {msg.jump_url}", color=discord.Color.dark_grey())
            await staff_channel.send(embed=audit)
        features = self.bot.get_cog("HorizonsFeatures")
        if features and isinstance(interaction.user, discord.Member) and interaction.guild:
            await features.check_achievements(interaction.guild, interaction.user)
        # Déblocage après publication effective et sauvegarde de l'idée.
        try:
            grant_sky_star(interaction.guild_id, interaction.user.id, "origins.idea")
        except Exception:
            _sky_log.exception("Carte du Ciel : impossible de créditer l'idée %s", idea_id)
        await interaction.response.send_message("Merci ! Ton idée a été déposée anonymement. 💡", ephemeral=True)

    @app_commands.command(name="mes_idees", description="Consulter tes propositions envoyées à la boîte à idées.")
    async def mes_idees(self, interaction: discord.Interaction):
        with db() as conn:
            rows = conn.execute("SELECT id,content,status,created_at FROM community_ideas WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10", (interaction.guild_id or 0, interaction.user.id)).fetchall()
        if not rows:
            await interaction.response.send_message("Tu n'as pas encore proposé d'idée.", ephemeral=True); return
        labels = {"received":"Reçue", "review":"En réflexion", "accepted":"Acceptée", "rejected":"Non retenue", "done":"Réalisée"}
        text = "\n\n".join(f"**#{r['id']} — {labels.get(r['status'], r['status'])}**\n{r['content'][:220]}" for r in rows)
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @app_commands.command(name="idee_statut", description="Mettre à jour le statut d'une idée (staff).")
    @app_commands.choices(statut=[app_commands.Choice(name="En réflexion",value="review"), app_commands.Choice(name="Acceptée",value="accepted"), app_commands.Choice(name="Non retenue",value="rejected"), app_commands.Choice(name="Réalisée",value="done")])
    async def idee_statut(self, interaction: discord.Interaction, identifiant: app_commands.Range[int,1,1000000], statut: app_commands.Choice[str]):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("Commande réservée au staff.", ephemeral=True); return
        with db() as conn:
            row = conn.execute("SELECT message_id,content FROM community_ideas WHERE id=? AND guild_id=?", (identifiant, interaction.guild_id or 0)).fetchone()
            if row: conn.execute("UPDATE community_ideas SET status=? WHERE id=?", (statut.value, identifiant))
        if not row:
            await interaction.response.send_message("Idée introuvable.", ephemeral=True); return
        channel = self.bot.get_channel(IDEAS_CHANNEL_ID)
        if channel is None:
            try: channel = await self.bot.fetch_channel(IDEAS_CHANNEL_ID)
            except discord.HTTPException: channel = None
        if isinstance(channel, (discord.TextChannel, discord.ForumChannel)) and row['message_id']:
            try:
                if isinstance(channel, discord.ForumChannel):
                    with db() as conn:
                        cols = {r[1] for r in conn.execute("PRAGMA table_info(community_ideas)")}
                        thread_row = conn.execute("SELECT thread_id FROM community_ideas WHERE id=?", (identifiant,)).fetchone() if 'thread_id' in cols else None
                    thread = channel.get_thread(thread_row['thread_id']) if thread_row and thread_row['thread_id'] else None
                    if thread is None and thread_row and thread_row['thread_id']:
                        thread = await self.bot.fetch_channel(thread_row['thread_id'])
                    if isinstance(thread, discord.Thread):
                        msg = await thread.fetch_message(row['message_id'])
                    else:
                        msg = None
                else:
                    msg = await channel.fetch_message(row['message_id'])
                if msg:
                    await msg.edit(embed=idea_embed(identifiant,row['content'],statut.value), view=IdeaVoteView(identifiant) if statut.value not in ('done','rejected') else None)
            except discord.HTTPException: pass
        with db() as conn:
            author_row = conn.execute("SELECT user_id FROM community_ideas WHERE id=? AND guild_id=?", (identifiant, interaction.guild_id or 0)).fetchone()
        if author_row and interaction.guild:
            author = interaction.guild.get_member(int(author_row["user_id"]))
            if author is None:
                try:
                    author = await interaction.guild.fetch_member(int(author_row["user_id"]))
                except discord.HTTPException:
                    author = None
            features = self.bot.get_cog("HorizonsFeatures")
            if features and isinstance(author, discord.Member):
                await features.check_achievements(interaction.guild, author)
        await interaction.response.send_message(f"Statut de l'idée #{identifiant} mis à jour : **{statut.name}**.", ephemeral=True)

    @app_commands.command(name="remercier", description="Remercier publiquement un membre sur le mur de la solidarité.")
    @app_commands.describe(membre="La personne que tu souhaites remercier", motif="Pourquoi souhaites-tu la remercier ?", message="Un petit mot personnel")
    @app_commands.choices(motif=[app_commands.Choice(name="Écoute et soutien",value="Écoute et soutien"), app_commands.Choice(name="Entraide",value="Entraide"), app_commands.Choice(name="Gentillesse",value="Gentillesse"), app_commands.Choice(name="Encouragement",value="Encouragement"), app_commands.Choice(name="Bonne humeur",value="Bonne humeur")])
    async def remercier(self, interaction: discord.Interaction, membre: discord.Member, motif: app_commands.Choice[str], message: app_commands.Range[str,5,700]):
        if membre.bot or membre.id == interaction.user.id:
            await interaction.response.send_message("Tu peux remercier un autre membre, pas un bot ni toi-même.", ephemeral=True); return
        channel = self.bot.get_channel(SOLIDARITY_CHANNEL_ID)
        if channel is None:
            try: channel = await self.bot.fetch_channel(SOLIDARITY_CHANNEL_ID)
            except discord.HTTPException: channel = None
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.response.send_message("Le salon forum du mur de la solidarité est introuvable.", ephemeral=True); return
        embed = horizons_embed(title="✦ Un merci sur le mur de la solidarité", description=message, color=discord.Color.from_rgb(190,90,160))
        embed.add_field(name="À", value=membre.mention, inline=True); embed.add_field(name="Pour", value=motif.value, inline=True)
        embed.add_field(name="De la part de", value=interaction.user.mention, inline=False); embed.set_footer(text="HORIZONS • La reconnaissance fait du bien")
        if isinstance(channel, discord.ForumChannel):
            created = await channel.create_thread(name=f"💜 Merci à {membre.display_name}", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
            posted = created.message
        else:
            posted = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        with db() as conn: conn.execute("INSERT INTO solidarity_thanks(guild_id,author_id,target_id,reason,message_id,created_at) VALUES(?,?,?,?,?,?)", (interaction.guild_id or 0,interaction.user.id,membre.id,motif.value,posted.id,datetime.now(timezone.utc).isoformat()))
        features = self.bot.get_cog("HorizonsFeatures")
        if features and interaction.guild:
            if isinstance(interaction.user, discord.Member):
                await features.check_achievements(interaction.guild, interaction.user)
            await features.check_achievements(interaction.guild, membre)
        # L'étoile récompense un remerciement effectivement publié, jamais un clic.
        try:
            grant_sky_star(interaction.guild_id or 0, interaction.user.id, "origins.recognition")
        except Exception:
            _sky_log.exception("Carte du Ciel : impossible de créditer le remerciement %s", posted.id)
        await interaction.response.send_message(f"Ton remerciement a été publié dans {channel.mention}. 💜", ephemeral=True)

    def dashboard_embed(self, guild: discord.Guild, section: str):
        with db() as conn:
            if section == "overview":
                ideas = conn.execute("SELECT COUNT(*) FROM community_ideas WHERE guild_id=? AND status IN ('received','review')", (guild.id,)).fetchone()[0]
                thanks = conn.execute("SELECT COUNT(*) FROM solidarity_thanks WHERE guild_id=?", (guild.id,)).fetchone()[0]
                tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE guild_id=? AND status='open'", (guild.id,)).fetchone()[0]
                events = conn.execute("SELECT COUNT(*) FROM events WHERE guild_id=? AND status='open'", (guild.id,)).fetchone()[0]
                e = horizons_embed(title="🛡️ HORIZONS — Tableau de bord", description=f"**Membres :** {guild.member_count or 'N/D'}\n**Idées à traiter :** {ideas}\n**Remerciements :** {thanks}\n**Tickets ouverts :** {tickets}\n**Événements ouverts :** {events}", color=discord.Color.blurple())
            elif section == "ideas":
                rows = conn.execute("SELECT id,status,content FROM community_ideas WHERE guild_id=? ORDER BY id DESC LIMIT 8", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` **{r['status']}** — {r['content'][:100]}" for r in rows) or "Aucune idée pour le moment."
                e = horizons_embed(title="💡 Suivi de la boîte à idées", description=body, color=discord.Color.gold())
            elif section == "solidarity":
                rows = conn.execute("SELECT target_id,reason,created_at FROM solidarity_thanks WHERE guild_id=? ORDER BY id DESC LIMIT 8", (guild.id,)).fetchall()
                body = "\n".join(f"<@{r['target_id']}> — {r['reason']}" for r in rows) or "Aucun remerciement pour le moment."
                e = horizons_embed(title="💜 Mur de la solidarité", description=body, color=discord.Color.magenta())
            elif section == "moderation":
                warnings = conn.execute("SELECT COUNT(*) FROM warnings WHERE guild_id=? AND active=1", (guild.id,)).fetchone()[0]
                e = horizons_embed(title="🛡️ Modération", description=f"**Avertissements actifs :** {warnings}\nLes actions de modération restent disponibles via les commandes dédiées.", color=discord.Color.orange())
            elif section == "tickets":
                rows = conn.execute("SELECT id,opener_id,subject,created_at FROM tickets WHERE guild_id=? AND status='open' ORDER BY id DESC LIMIT 8", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` <@{r['opener_id']}> — {r['subject'][:90]}" for r in rows) or "Aucun ticket ouvert."
                e = horizons_embed(title="🎫 Tickets ouverts", description=body, color=discord.Color.teal())
            else:
                rows = conn.execute("SELECT id,title,starts_at FROM events WHERE guild_id=? AND status='open' ORDER BY starts_at LIMIT 8", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` **{r['title']}** — {r['starts_at']}" for r in rows) or "Aucun événement ouvert."
                e = horizons_embed(title="📅 Événements", description=body, color=discord.Color.green())
        e.set_footer(text="HORIZONS • Tableau de bord privé du staff")
        return e


async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityHub(bot))
