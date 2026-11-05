"""Giveaways HORIZONS : création avec image, inscriptions persistantes et tirages."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
import json
import logging
import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import STAFF_ROLE_ID
from .storage import db

log = logging.getLogger(__name__)
GIVEAWAY_CHANNEL_ID = 1566562183490441326

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def staff_allowed(member: discord.abc.User) -> bool:
    return isinstance(member, discord.Member) and (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_messages
        or member.guild_permissions.manage_guild
        or (STAFF_ROLE_ID and any(role.id == STAFF_ROLE_ID for role in member.roles))
    )

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="Participer", emoji="🎉", style=discord.ButtonStyle.success,
            custom_id=f"horizons:giveaway:join:{giveaway_id}", disabled=disabled,
        )
        button.callback = self.join
        self.add_item(button)
        self.giveaway_id = giveaway_id

    async def join(self, interaction: discord.Interaction):
        with db() as conn:
            row = conn.execute(
                "SELECT status,ends_at,required_role_id FROM giveaways WHERE id=? AND guild_id=?",
                (self.giveaway_id, interaction.guild_id or 0),
            ).fetchone()
            if not row or row["status"] != "open" or datetime.fromisoformat(row["ends_at"]) <= utcnow():
                await interaction.response.send_message("Ce giveaway est terminé ou n'est plus disponible.", ephemeral=True)
                return
            if row["required_role_id"]:
                if not isinstance(interaction.user, discord.Member) or int(row["required_role_id"]) not in {r.id for r in interaction.user.roles}:
                    await interaction.response.send_message("Tu ne possèdes pas le rôle requis pour participer à ce giveaway.", ephemeral=True)
                    return
            cur = conn.execute(
                "INSERT OR IGNORE INTO giveaway_entries(giveaway_id,user_id,created_at) VALUES(?,?,?)",
                (self.giveaway_id, interaction.user.id, utcnow().isoformat()),
            )
        if cur.rowcount:
            await interaction.response.send_message("Ta participation est bien enregistrée ! Bonne chance 🍀", ephemeral=True)
        else:
            await interaction.response.send_message("Tu participes déjà à ce giveaway. Bonne chance ! 🍀", ephemeral=True)

class Giveaways(commands.Cog):
    giveaway = app_commands.Group(name="giveaway", description="Gérer les giveaways HORIZONS")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.finish_due.start()

    async def cog_load(self):
        with db() as conn:
            rows = conn.execute("SELECT id,message_id FROM giveaways WHERE status='open' AND message_id IS NOT NULL").fetchall()
        for row in rows:
            self.bot.add_view(GiveawayView(int(row["id"])), message_id=int(row["message_id"]))

    def cog_unload(self):
        self.finish_due.cancel()

    @giveaway.command(name="creer", description="Créer un giveaway avec une image facultative.")
    @app_commands.describe(
        lot="Le lot à gagner", duree_heures="Durée du giveaway, de 1 à 720 heures",
        gagnants="Nombre de gagnants", description="Informations ou règles complémentaires",
        image="Image à afficher sur le giveaway (facultative)",
        role_requis="Rôle obligatoire pour participer (facultatif)",
    )
    async def creer(
        self, interaction: discord.Interaction,
        lot: str,
        duree_heures: app_commands.Range[int, 1, 720],
        gagnants: app_commands.Range[int, 1, 10] = 1,
        description: str = "",
        image: discord.Attachment | None = None,
        role_requis: discord.Role | None = None,
    ):
        if not staff_allowed(interaction.user):
            await interaction.response.send_message("Cette commande est réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande doit être utilisée sur HORIZONS.", ephemeral=True)
            return
        if not 3 <= len(lot.strip()) <= 200:
            await interaction.response.send_message("Le nom du lot doit contenir entre 3 et 200 caractères.", ephemeral=True)
            return
        if len(description) > 1000:
            await interaction.response.send_message("La description ne peut pas dépasser 1 000 caractères.", ephemeral=True)
            return
        if image and not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message("Le fichier joint doit être une image (PNG, JPG, GIF ou WEBP).", ephemeral=True)
            return
        channel = self.bot.get_channel(GIVEAWAY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(GIVEAWAY_CHANNEL_ID)
            except discord.HTTPException:
                channel = None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Je ne trouve pas le salon #Giveaways ou il n'est pas textuel.", ephemeral=True)
            return
        end = utcnow() + timedelta(hours=duree_heures)
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO giveaways(guild_id,channel_id,creator_id,prize,winners_count,ends_at,created_at,description,image_url,required_role_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (interaction.guild_id, channel.id, interaction.user.id, lot.strip(), gagnants,
                 end.isoformat(), utcnow().isoformat(), description.strip(), image.url if image else None,
                 role_requis.id if role_requis else None),
            )
            giveaway_id = int(cur.lastrowid)
        embed = horizons_embed(
            title="🎉 GIVEAWAY HORIZONS",
            description=f"**🎁 Lot à gagner :** {lot.strip()}\n\n{description.strip() or 'Tente ta chance en cliquant sur le bouton ci-dessous !'}",
            color=discord.Color.gold(), timestamp=utcnow(),
        )
        embed.add_field(name="⏳ Fin du giveaway", value=discord.utils.format_dt(end, style="F"), inline=False)
        embed.add_field(name="🏆 Gagnant(s)", value=str(gagnants), inline=True)
        embed.add_field(name="👥 Participants", value="0", inline=True)
        if role_requis:
            embed.add_field(name="🔐 Condition", value=f"Rôle requis : {role_requis.mention}", inline=False)
        embed.set_footer(text=f"Giveaway #{giveaway_id} • HORIZONS")
        if image:
            embed.set_image(url=image.url)
        await interaction.response.defer(ephemeral=True)
        try:
            message = await channel.send(embed=embed, view=GiveawayView(giveaway_id))
        except discord.HTTPException:
            with db() as conn:
                conn.execute("UPDATE giveaways SET status='failed' WHERE id=?", (giveaway_id,))
            await interaction.followup.send("Discord n'a pas accepté la publication. Vérifie les permissions du bot.", ephemeral=True)
            return
        with db() as conn:
            conn.execute("UPDATE giveaways SET message_id=? WHERE id=?", (message.id, giveaway_id))
        self.bot.add_view(GiveawayView(giveaway_id), message_id=message.id)
        await interaction.followup.send(f"✅ Giveaway **#{giveaway_id}** publié dans {channel.mention}.", ephemeral=True)

    @giveaway.command(name="annuler", description="Annuler un giveaway en cours.")
    @app_commands.describe(numero="Numéro du giveaway")
    async def annuler(self, interaction: discord.Interaction, numero: app_commands.Range[int, 1, 999999]):
        if not staff_allowed(interaction.user):
            await interaction.response.send_message("Commande réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            row = conn.execute("SELECT channel_id,message_id FROM giveaways WHERE id=? AND guild_id=? AND status='open'", (numero, interaction.guild_id or 0)).fetchone()
            if row:
                conn.execute("UPDATE giveaways SET status='cancelled' WHERE id=?", (numero,))
        if not row:
            await interaction.response.send_message("Aucun giveaway ouvert ne correspond à ce numéro.", ephemeral=True)
            return
        channel = self.bot.get_channel(int(row["channel_id"]))
        if channel and row["message_id"]:
            try:
                msg = await channel.fetch_message(int(row["message_id"]))
                await msg.edit(content="⛔ Giveaway annulé par l'équipe HORIZONS.", view=GiveawayView(numero, disabled=True))
            except discord.HTTPException:
                pass
        await interaction.response.send_message(f"Le giveaway **#{numero}** a été annulé.", ephemeral=True)

    @giveaway.command(name="reroll", description="Effectuer un nouveau tirage parmi les participants.")
    @app_commands.describe(numero="Numéro du giveaway terminé")
    async def reroll(self, interaction: discord.Interaction, numero: app_commands.Range[int, 1, 999999]):
        if not staff_allowed(interaction.user):
            await interaction.response.send_message("Commande réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            row = conn.execute("SELECT * FROM giveaways WHERE id=? AND guild_id=? AND status='closed'", (numero, interaction.guild_id or 0)).fetchone()
            entries = conn.execute("SELECT user_id FROM giveaway_entries WHERE giveaway_id=?", (numero,)).fetchall() if row else []
        if not row:
            await interaction.response.send_message("Ce giveaway n'existe pas ou n'est pas terminé.", ephemeral=True)
            return
        guild = interaction.guild
        eligible = []
        for entry in entries:
            member = guild.get_member(int(entry["user_id"])) if guild else None
            if member is None and guild:
                try:
                    member = await guild.fetch_member(int(entry["user_id"]))
                except discord.HTTPException:
                    continue
            if member and (not row["required_role_id"] or int(row["required_role_id"]) in {r.id for r in member.roles}):
                eligible.append(member)
        if not eligible:
            await interaction.response.send_message("Aucun participant encore éligible pour effectuer un nouveau tirage.", ephemeral=True)
            return
        previous = set(json.loads(row["winners_json"] or "[]"))
        pool = [m for m in eligible if m.id not in previous] or eligible
        winners = random.sample(pool, min(int(row["winners_count"]), len(pool)))
        with db() as conn:
            conn.execute("UPDATE giveaways SET winners_json=? WHERE id=?", (json.dumps([m.id for m in winners]), numero))
        await interaction.response.send_message("🎊 Nouveau tirage : " + ", ".join(m.mention for m in winners), allowed_mentions=discord.AllowedMentions(users=True))

    @tasks.loop(minutes=1)
    async def finish_due(self):
        now = utcnow()
        with db() as conn:
            rows = conn.execute("SELECT * FROM giveaways WHERE status='open' AND ends_at<=?", (now.isoformat(),)).fetchall()
        for row in rows:
            guild = self.bot.get_guild(int(row["guild_id"]))
            channel = self.bot.get_channel(int(row["channel_id"]))
            message = None
            if channel and row["message_id"]:
                try:
                    message = await channel.fetch_message(int(row["message_id"]))
                except discord.HTTPException:
                    pass
            entries = []
            with db() as conn:
                entries = conn.execute("SELECT user_id FROM giveaway_entries WHERE giveaway_id=?", (row["id"],)).fetchall()
            eligible = []
            if guild:
                for entry in entries:
                    member = guild.get_member(int(entry["user_id"]))
                    if member is None:
                        try:
                            member = await guild.fetch_member(int(entry["user_id"]))
                        except discord.HTTPException:
                            continue
                    if not row["required_role_id"] or int(row["required_role_id"]) in {r.id for r in member.roles}:
                        eligible.append(member)
            winners = random.sample(eligible, min(len(eligible), int(row["winners_count"]))) if eligible else []
            with db() as conn:
                conn.execute("UPDATE giveaways SET status='closed',winners_json=? WHERE id=?", (json.dumps([m.id for m in winners]), row["id"]))
            if channel:
                try:
                    if winners:
                        await channel.send(f"🎊 Le giveaway **{row['prize']}** est terminé ! Félicitations à " + ", ".join(m.mention for m in winners) + " !")
                    else:
                        await channel.send(f"Le giveaway **{row['prize']}** est terminé, mais aucun participant éligible n'a été trouvé.")
                    if message:
                        await message.edit(view=GiveawayView(int(row["id"]), disabled=True))
                except discord.HTTPException:
                    log.exception("Impossible de publier le résultat du giveaway #%s", row["id"])

    @finish_due.before_loop
    async def before_finish_due(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
