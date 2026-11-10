"""Saisons communautaires HORIZONS : missions, objectifs collectifs et récompenses."""
from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import GUILD_ID, STAFF_ROLE_ID, MISSIONS_CHANNEL_ID, COLLECTIVE_CHALLENGES_CHANNEL_ID, AGENDA_CHANNEL_ID, LOCAL_TIMEZONE
from cogs.embed_theme import horizons_embed
from .storage import db

SEASON_DAYS = 42
COLLECTIVE_TARGET = 60
UNIQUE_MEMBER_TARGET = 20
WEEKLY_MISSIONS = {
    1: ("Découvrir un espace HORIZONS que tu ne connais pas encore", "Partager une passion, une idée ou une recommandation", "Faire un premier pas vers un autre membre, à ton rythme"),
    2: ("Participer à une discussion qui t'intéresse", "Découvrir une activité ou un jeu proposé sur le serveur", "Accueillir ou encourager un membre"),
    3: ("Proposer un sujet de discussion", "Participer à un quiz ou à une animation", "Partager une découverte culturelle ou musicale"),
    4: ("Rejoindre un échange collectif", "Aider à faire vivre un salon", "Faire découvrir une passion à la communauté"),
    5: ("Participer à un défi collectif", "Remercier ou valoriser une personne", "Proposer une idée pour la suite d'HORIZONS"),
    6: ("Revenir sur une activité que tu as appréciée", "Partager un souvenir positif de la saison", "Participer au rendez-vous de clôture ou à son fil de discussion"),
}
MILESTONES = ((15, "🌱 Premier élan"), (30, "🌿 L'énergie collective"), (45, "🌳 Un bel horizon"), (60, "✨ Saison accomplie"))


def now_local() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def staff_ok(member: discord.Member) -> bool:
    return member.guild_permissions.administrator or bool(STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles))


async def fetch_text_channel(bot: commands.Bot, channel_id: int):
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
    return channel if isinstance(channel, (discord.TextChannel, discord.ForumChannel)) else None


class Seasons(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.season_watch.start()

    def cog_unload(self):
        self.season_watch.cancel()

    async def cog_load(self):
        # Tables are created by storage.init_db before extensions are loaded.
        pass

    async def publish(self, title: str, description: str, *, color: discord.Color = discord.Color.blurple(), channel_ids=None):
        sent = 0
        seen = set()
        for channel_id in (channel_ids if channel_ids is not None else (AGENDA_CHANNEL_ID, MISSIONS_CHANNEL_ID)):
            if not channel_id or channel_id in seen:
                continue
            seen.add(channel_id)
            channel = await fetch_text_channel(self.bot, channel_id)
            if channel is None:
                continue
            embed = horizons_embed(title=title, description=description, color=color)
            embed.set_footer(text="HORIZONS • Une aventure collective, chacun à son rythme")
            try:
                if isinstance(channel, discord.ForumChannel):
                    await channel.create_thread(name=title[:95], content=description, embed=embed)
                else:
                    await channel.send(embed=embed)
                sent += 1
            except discord.HTTPException:
                continue
        return sent

    def active_season(self, guild_id: int):
        with db() as conn:
            return conn.execute("SELECT * FROM horizons_seasons WHERE guild_id=? AND status='active' ORDER BY id DESC LIMIT 1", (guild_id,)).fetchone()

    def season_week(self, season) -> int:
        start = datetime.fromisoformat(season["starts_at"])
        elapsed = max(0, (now_local() - start).days)
        return min(SEASON_DAYS // 7, elapsed // 7 + 1)

    async def progress(self, season_id: int):
        with db() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM horizons_season_completions WHERE season_id=?", (season_id,)).fetchone()["n"]
            members = conn.execute("SELECT COUNT(DISTINCT user_id) AS n FROM horizons_season_participants WHERE season_id=?", (season_id,)).fetchone()["n"]
        return int(count), int(members)

    async def check_milestones(self, guild: discord.Guild, season, count: int, members: int):
        for threshold, label in MILESTONES:
            if count < threshold:
                continue
            with db() as conn:
                inserted = conn.execute("INSERT OR IGNORE INTO horizons_season_milestones(season_id,threshold,reached_at) VALUES(?,?,?)", (season["id"], threshold, now_local().isoformat())).rowcount
            if inserted:
                await self.publish(f"🎉 Objectif collectif débloqué : {label}", f"La communauté vient de valider **{threshold}/{COLLECTIVE_TARGET} étapes** ! Merci à toutes les personnes qui contribuent à cette saison. Prochain cap : **{min(threshold + 15, COLLECTIVE_TARGET)} étapes**.", color=discord.Color.gold(), channel_ids=(COLLECTIVE_CHALLENGES_CHANNEL_ID,))
        if members >= UNIQUE_MEMBER_TARGET:
            with db() as conn:
                inserted = conn.execute("INSERT OR IGNORE INTO horizons_season_milestones(season_id,threshold,reached_at) VALUES(?,-20,?)", (season["id"], now_local().isoformat())).rowcount
            if inserted:
                await self.publish("🤝 Objectif des 20 membres atteint !", f"Nous sommes désormais **{UNIQUE_MEMBER_TARGET} membres participants** à cette saison. Merci d'avoir fait un bout de chemin ensemble ! 💜", color=discord.Color.gold(), channel_ids=(COLLECTIVE_CHALLENGES_CHANNEL_ID,))

    async def announce_week(self, season, week: int):
        with db() as conn:
            already = conn.execute("SELECT 1 FROM horizons_season_week_announcements WHERE season_id=? AND week_number=?", (season["id"], week)).fetchone()
        if already:
            return
        missions = WEEKLY_MISSIONS.get(week, WEEKLY_MISSIONS[6])
        description = f"**{season['title']} — semaine {week}/6**\n\n" + "\n".join(f"**Étape {i}.** {mission}" for i, mission in enumerate(missions, 1)) + "\n\nPour suivre ta progression : `/centre` → Mes activités → Saison. Tu peux choisir les étapes qui te correspondent et avancer sans pression. 💜"
        sent = await self.publish(f"🧭 Les étapes de la semaine {week}", description, channel_ids=(MISSIONS_CHANNEL_ID,))
        if sent:
            with db() as conn:
                conn.execute("INSERT OR IGNORE INTO horizons_season_week_announcements(season_id,week_number,posted_at) VALUES(?,?,?)", (season["id"], week, now_local().isoformat()))

    @tasks.loop(minutes=10)
    async def season_watch(self):
        if not GUILD_ID:
            return
        season = self.active_season(GUILD_ID)
        if not season:
            return
        end = datetime.fromisoformat(season["ends_at"])
        if now_local() < end:
            await self.announce_week(season, self.season_week(season))
            return
        with db() as conn:
            conn.execute("UPDATE horizons_seasons SET status='closed',closed_at=? WHERE id=? AND status='active'", (now_local().isoformat(), season["id"]))
            already = conn.execute("SELECT 1 FROM horizons_season_milestones WHERE season_id=? AND threshold=-1", (season["id"],)).fetchone()
            if not already:
                conn.execute("INSERT INTO horizons_season_milestones(season_id,threshold,reached_at) VALUES(?,-1,?)", (season["id"], now_local().isoformat()))
        count, members = await self.progress(season["id"])
        await self.publish(f"🏁 Clôture de la saison : {season['title']}", f"Notre aventure de six semaines se termine !\n\n**{count}/{COLLECTIVE_TARGET} étapes validées**\n**{members} membres participants**\n\nMerci d'avoir contribué, même par un seul petit pas. Les récompenses personnelles sont consultables avec `/centre` → Mes activités → Saison. La prochaine saison sera annoncée prochainement. 💜", color=discord.Color.gold())

    @season_watch.before_loop
    async def before_season_watch(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="saison", description="Découvrir la saison HORIZONS en cours et son objectif collectif.")
    async def saison(self, interaction: discord.Interaction):
        season = self.active_season(interaction.guild_id or 0)
        if not season:
            await interaction.response.send_message("Aucune saison n'est actuellement ouverte. La prochaine aventure sera annoncée ici. 🌅", ephemeral=True)
            return
        count, members = await self.progress(season["id"])
        week = self.season_week(season)
        end = datetime.fromisoformat(season["ends_at"])
        embed = horizons_embed(title=f"🌅 {season['title']}", description=season["description"], color=discord.Color.blurple())
        embed.add_field(name="Semaine", value=f"{min(week, 6)}/6", inline=True)
        embed.add_field(name="Fin prévue", value=discord.utils.format_dt(end, style="D"), inline=True)
        embed.add_field(name="Objectif collectif", value=f"**{count}/{COLLECTIVE_TARGET} étapes**\n**{members}/{UNIQUE_MEMBER_TARGET} membres**", inline=False)
        embed.add_field(name="Pour participer", value="Utilise `/centre` → Mes activités → Saison, puis `/centre` → Mes activités → Saison et `/centre` → Mes activités → Saison.", inline=False)
        embed.add_field(name="Récompenses collectives", value="🌱 15 étapes • 🌿 30 • 🌳 45 • ✨ 60 étapes", inline=False)
        embed.set_footer(text="Aucune connexion quotidienne obligatoire • Chaque contribution compte")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def rejoindre_saison(self, interaction: discord.Interaction):
        season = self.active_season(interaction.guild_id or 0)
        if not season:
            await interaction.response.send_message("Il n'y a pas de saison ouverte actuellement.", ephemeral=True)
            return
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO horizons_season_participants(season_id,guild_id,user_id,joined_at) VALUES(?,?,?,?)", (season["id"], interaction.guild_id, interaction.user.id, now_local().isoformat()))
        await interaction.response.send_message("Bienvenue dans cette aventure ! 💜 Tu peux avancer à ton rythme et consulter `/centre` → Mes activités → Saison quand tu le souhaites.", ephemeral=True)

    async def missions_saison(self, interaction: discord.Interaction):
        season = self.active_season(interaction.guild_id or 0)
        if not season:
            await interaction.response.send_message("Aucune saison n'est ouverte actuellement.", ephemeral=True)
            return
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO horizons_season_participants(season_id,guild_id,user_id,joined_at) VALUES(?,?,?,?)", (season["id"], interaction.guild_id, interaction.user.id, now_local().isoformat()))
            rows = conn.execute("SELECT mission_number FROM horizons_season_completions WHERE season_id=? AND user_id=? AND week_number=?", (season["id"], interaction.user.id, self.season_week(season))).fetchall()
        completed = {int(row["mission_number"]) for row in rows}
        week = self.season_week(season)
        missions = WEEKLY_MISSIONS.get(week, WEEKLY_MISSIONS[6])
        embed = horizons_embed(title=f"🧭 Tes missions — semaine {week}", description=f"**{season['title']}**\nChoisis les petits pas qui te parlent. Tu n'as pas besoin de tout faire.", color=discord.Color.blurple())
        for i, mission in enumerate(missions, 1):
            embed.add_field(name=f"{'✅' if i in completed else '⬜'} Étape {i}", value=mission, inline=False)
        embed.set_footer(text="Validation sur l'honneur • Pas de classement • Pas de pression")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def valider_etape_saison(self, interaction: discord.Interaction, etape: app_commands.Choice[int]):
        season = self.active_season(interaction.guild_id or 0)
        if not season:
            await interaction.response.send_message("Aucune saison n'est ouverte actuellement.", ephemeral=True)
            return
        week = self.season_week(season)
        mission = WEEKLY_MISSIONS.get(week, WEEKLY_MISSIONS[6])[etape.value - 1]
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO horizons_season_participants(season_id,guild_id,user_id,joined_at) VALUES(?,?,?,?)", (season["id"], interaction.guild_id, interaction.user.id, now_local().isoformat()))
            inserted = conn.execute("INSERT OR IGNORE INTO horizons_season_completions(season_id,guild_id,user_id,week_number,mission_number,completed_at) VALUES(?,?,?,?,?,?)", (season["id"], interaction.guild_id, interaction.user.id, week, etape.value, now_local().isoformat())).rowcount
            total_user = conn.execute("SELECT COUNT(*) AS n FROM horizons_season_completions WHERE season_id=? AND user_id=?", (season["id"], interaction.user.id)).fetchone()["n"]
            if total_user >= 3:
                conn.execute("INSERT OR IGNORE INTO horizons_season_rewards(season_id,guild_id,user_id,reward_key,unlocked_at) VALUES(?,?,?,'premiers_pas',?)", (season["id"], interaction.guild_id, interaction.user.id, now_local().isoformat()))
            if total_user >= 9:
                conn.execute("INSERT OR IGNORE INTO horizons_season_rewards(season_id,guild_id,user_id,reward_key,unlocked_at) VALUES(?,?,?,'explorateur',?)", (season["id"], interaction.guild_id, interaction.user.id, now_local().isoformat()))
        if not inserted:
            await interaction.response.send_message("Cette étape est déjà validée pour cette semaine. 🌟", ephemeral=True)
            return
        count, members = await self.progress(season["id"])
        await self.check_milestones(interaction.guild, season, count, members)
        msg = f"Étape validée : **{mission}** 🌱\nObjectif collectif : **{count}/{COLLECTIVE_TARGET}** étapes, avec **{members}** membres participants."
        if total_user >= 3:
            msg += "\n🏅 Tu as débloqué ou conservé la distinction **Premiers pas**."
        if total_user >= 9:
            msg += "\n🧭 Tu as débloqué ou conservé la distinction **Explorateur HORIZONS**."
        await interaction.response.send_message(msg, ephemeral=True)

    async def mes_recompenses_saison(self, interaction: discord.Interaction):
        with db() as conn:
            rows = conn.execute("SELECT s.title,r.reward_key,r.unlocked_at FROM horizons_season_rewards r JOIN horizons_seasons s ON s.id=r.season_id WHERE r.guild_id=? AND r.user_id=? ORDER BY r.unlocked_at DESC LIMIT 20", (interaction.guild_id or 0, interaction.user.id)).fetchall()
        labels = {"premiers_pas": "🌱 Premiers pas", "explorateur": "🧭 Explorateur HORIZONS"}
        if not rows:
            await interaction.response.send_message("Tu n'as pas encore de distinction saisonnière. Chaque contribution compte, même toute petite. 💜", ephemeral=True)
            return
        lines = [f"**{labels.get(row['reward_key'], row['reward_key'])}** — {row['title']}" for row in rows]
        await interaction.response.send_message("🏅 **Tes distinctions HORIZONS**\n" + "\n".join(lines), ephemeral=True)

    @app_commands.command(name="saison_lancer", description="Lancer une nouvelle saison HORIZONS (équipe uniquement).")
    @app_commands.describe(titre="Nom de la saison", description="Thème et intention de la saison")
    async def saison_lancer(self, interaction: discord.Interaction, titre: app_commands.Range[str, 3, 80], description: app_commands.Range[str, 10, 900]):
        if not isinstance(interaction.user, discord.Member) or not staff_ok(interaction.user):
            await interaction.response.send_message("Cette commande est réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        if self.active_season(interaction.guild_id or 0):
            await interaction.response.send_message("Une saison est déjà active. Clôture-la avant d'en lancer une autre.", ephemeral=True)
            return
        start = now_local()
        end = start + timedelta(days=SEASON_DAYS)
        with db() as conn:
            cur = conn.execute("INSERT INTO horizons_seasons(guild_id,title,description,starts_at,ends_at,status,created_by,created_at) VALUES(?,?,?,?,?,'active',?,?)", (interaction.guild_id, titre, description, start.isoformat(), end.isoformat(), interaction.user.id, start.isoformat()))
            season_id = cur.lastrowid
        await interaction.response.send_message(f"La saison **{titre}** est lancée. L'annonce de lancement est en cours de publication. 🌅", ephemeral=True)
        await self.publish(f"🌅 Ouverture de la saison HORIZONS : {titre}", f"{description}\n\n**Durée :** 6 semaines, jusqu'au {end.strftime('%d/%m/%Y')}\n**Objectif collectif :** 60 étapes validées et 20 membres participants.\n\nPour prendre part à l'aventure : `/centre` → Mes activités → Saison, puis `/centre` → Mes activités → Saison.\n\n**Les quatre caps collectifs :** 15, 30, 45 et 60 étapes. Chaque membre avance à son rythme.\n\nLa grande clôture sera annoncée à la fin de la saison. 💜", color=discord.Color.green())
        await self.announce_week(self.active_season(interaction.guild_id or 0), 1)

    @app_commands.command(name="saison_clore", description="Clôturer immédiatement la saison en cours (équipe uniquement).")
    async def saison_clore(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not staff_ok(interaction.user):
            await interaction.response.send_message("Cette commande est réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        season = self.active_season(interaction.guild_id or 0)
        if not season:
            await interaction.response.send_message("Aucune saison active à clôturer.", ephemeral=True)
            return
        with db() as conn:
            conn.execute("UPDATE horizons_seasons SET status='closed',closed_at=? WHERE id=?", (now_local().isoformat(), season["id"]))
        count, members = await self.progress(season["id"])
        await interaction.response.send_message(f"La saison **{season['title']}** est clôturée. Résultat : {count} étapes, {members} membres.", ephemeral=True)
        await self.publish(f"🏁 Clôture de la saison : {season['title']}", f"Notre aventure se termine !\n\n**{count}/{COLLECTIVE_TARGET} étapes validées**\n**{members} membres participants**\n\nMerci d'avoir contribué, même par un seul petit pas. Consulte `/centre` → Mes activités → Saison pour retrouver tes distinctions. 💜", color=discord.Color.gold())


async def setup(bot: commands.Bot):
    await bot.add_cog(Seasons(bot))
