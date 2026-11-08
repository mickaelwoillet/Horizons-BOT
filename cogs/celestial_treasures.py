"""Cartes à gratter, collection des 20 étoiles et constellations HORIZONS."""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import LOCAL_TIMEZONE
from cogs.embed_theme import horizons_embed
from cogs.storage import db
from cogs.horizons_arcade import award_xp, total_xp, xp_level

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "data" / "assets" / "celestial"
CARD_ART = ASSETS / "carte_celeste.png"
REWARD_ART = {
    "thought": ASSETS / "recompense_thought.png",
    "star": ASSETS / "recompense_star.png",
    "dust": ASSETS / "recompense_dust.png",
    "xp": ASSETS / "recompense_xp.png",
    "fragment": ASSETS / "recompense_fragment.png",
    "surprise": ASSETS / "recompense_surprise.png",
}

STARS = {
    "aube": ("Aube", "Les nouveaux départs", "Chaque matin offre une page qui n'attend que toi.", "🌅"),
    "esperance": ("Espérance", "La confiance en demain", "Même dans la nuit, une lueur peut guider les pas.", "🌠"),
    "courage": ("Courage", "La force d'avancer", "Le courage n'efface pas la peur : il permet d'avancer avec elle.", "🦁"),
    "serenite": ("Sérénité", "La paix intérieure", "Prendre son temps est parfois la plus belle des victoires.", "🕊️"),
    "liberte": ("Liberté", "Être soi-même", "Ta lumière n'a pas à ressembler à celle des autres.", "🦋"),
    "ecoute": ("Écoute", "Accueillir l'autre", "Une présence attentive peut déjà tout changer.", "👂"),
    "amitie": ("Amitié", "La valeur du lien", "Les chemins sont plus doux lorsqu'ils se croisent.", "🤝"),
    "tendresse": ("Tendresse", "La douceur", "La douceur est une force qui sait prendre soin.", "💗"),
    "sagesse": ("Sagesse", "L'expérience", "Chaque expérience peut devenir une lumière pour demain.", "📖"),
    "harmonie": ("Harmonie", "L'équilibre", "Trouver son rythme, c'est déjà trouver un peu d'équilibre.", "☯️"),
    "reve": ("Rêve", "L'imagination", "Les horizons commencent souvent dans l'imagination.", "💭"),
    "confiance": ("Confiance", "Croire en soi", "Tu as le droit d'apprendre à croire en tes propres ressources.", "✨"),
    "bienveillance": ("Bienveillance", "La gentillesse", "Un geste bienveillant peut illuminer une journée entière.", "🌷"),
    "resilience": ("Résilience", "Se relever", "Les cicatrices racontent aussi les chemins parcourus.", "🔥"),
    "joie": ("Joie", "La lumière du quotidien", "Les petits bonheurs méritent eux aussi d'être célébrés.", "☀️"),
    "mystere": ("Mystère", "La curiosité", "La curiosité ouvre des portes que l'on ne soupçonnait pas.", "🔮"),
    "partage": ("Partage", "Donner et recevoir", "Ce que l'on partage prend souvent une autre dimension.", "🎁"),
    "unite": ("Unité", "La force du collectif", "Ensemble, les petites lumières deviennent un ciel.", "🌌"),
    "eternite": ("Éternité", "Les liens durables", "Certains souvenirs continuent de briller longtemps.", "♾️"),
    "horizons": ("HORIZONS", "Toutes les étoiles réunies", "Chaque membre apporte sa lumière. Ensemble, nous dessinons HORIZONS.", "🌟"),
}
CONSTELLATIONS = {
    "origines": ("🌅 Les Origines", ["aube", "esperance", "courage", "serenite"], "🌅 Éclat des Origines"),
    "liens": ("💗 Les Liens", ["liberte", "ecoute", "amitie", "tendresse"], "💗 Gardien des Liens"),
    "forces": ("🔥 Les Forces", ["sagesse", "harmonie", "reve", "confiance"], "🔥 Gardien des Forces"),
    "lumieres": ("✨ Les Lumières", ["bienveillance", "resilience", "joie", "mystere"], "✨ Porteur de Lumière"),
    "infini": ("🌌 L'Infini", ["partage", "unite", "eternite", "horizons"], "🌌 Gardien de l'Infini"),
}
STAR_PITY_LIMIT = 12
REWARD_WEIGHTS = {"thought": 40, "dust": 25, "xp": 15, "star": 12, "fragment": 7, "surprise": 1}

# Récompenses de collection : souvenirs narratifs et visuels, sans inflation
# de poussière/XP/cartes. Les rôles automatiques restent les récompenses sociales.
COLLECTION_REWARDS = {
    "origines": ("🌅 Mémoire des Origines", "Les premiers éclats ont tracé le chemin. Tu as réuni Aube, Espérance, Courage et Sérénité : ton voyage a trouvé sa première constellation.", "souvenir_origines.png"),
    "liens": ("💗 Mémoire des Liens", "Liberté, Écoute, Amitié et Tendresse brillent ensemble. Cette constellation célèbre les rencontres qui donnent un sens au voyage.", "souvenir_liens.png"),
    "forces": ("🔥 Mémoire des Forces", "Sagesse, Harmonie, Rêve et Confiance sont réunies. Cette constellation rappelle que la force peut aussi être douce et réfléchie.", "souvenir_forces.png"),
    "lumieres": ("✨ Mémoire des Lumières", "Bienveillance, Résilience, Joie et Mystère illuminent ton ciel. Une lumière partagée peut en faire naître bien d'autres.", "souvenir_lumieres.png"),
    "infini": ("🌌 Mémoire de l'Infini", "Partage, Unité, Éternité et HORIZONS sont réunies. Cette constellation célèbre ce qui grandit lorsque chacun apporte sa lumière.", "souvenir_infini.png"),
    "complete": ("🌟 Le Ciel HORIZONS", "Tu as réuni les 20 étoiles. Ton parcours devient un témoignage de patience, de curiosité et de lumière partagée. Le ciel HORIZONS est désormais complet.", "souvenir_complet.png"),
}


def choose_star_key(owned: set[str], consecutive_duplicates: int, rng=random) -> tuple[str, bool]:
    """Tirage uniforme ; après 12 doublons consécutifs, garantit une étoile manquante."""
    missing = [key for key in STARS if key not in owned]
    if missing and consecutive_duplicates >= STAR_PITY_LIMIT:
        return rng.choice(missing), True
    return rng.choice(list(STARS)), False


POSITIVE_THOUGHTS = [
    "Tu n'as pas besoin de tout accomplir aujourd'hui. Un petit pas compte déjà.",
    "Ta présence a de la valeur, même les jours où tu en doutes.",
    "Tu as le droit de faire une pause et de reprendre ton souffle.",
    "Les belles rencontres commencent parfois par un simple bonjour.",
    "Chaque journée peut contenir une petite lumière inattendue.",
    "Sois aussi patient avec toi-même que tu le serais avec un ami.",
]


def today_key() -> str:
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def get_ludic_setting(guild_id: int, key: str):
    with db() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (f"ludic:{guild_id}:{key}",)).fetchone()
    return json.loads(row[0]) if row else None


def add_dust(guild_id: int, user_id: int, amount: int) -> int:
    with db() as conn:
        conn.execute("INSERT INTO celestial_dust(guild_id,user_id,dust) VALUES(?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET dust=dust+excluded.dust", (guild_id, user_id, amount))
        row = conn.execute("SELECT dust FROM celestial_dust WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
        return int(row[0])


def dust_balance(guild_id: int, user_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT dust FROM celestial_dust WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
        return int(row[0]) if row else 0


def owned_stars(guild_id: int, user_id: int) -> set[str]:
    with db() as conn:
        rows = conn.execute("SELECT star_key FROM celestial_stars WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchall()
    return {row[0] for row in rows}


async def award_star_roles(guild: discord.Guild, member: discord.Member) -> list[str]:
    roles_map = get_ludic_setting(guild.id, "constellation_role_ids") or {}
    owned = owned_stars(guild.id, member.id)
    earned = []
    for key, (label, stars, role_name) in CONSTELLATIONS.items():
        if set(stars).issubset(owned):
            role_id = roles_map.get(role_name)
            role = guild.get_role(int(role_id)) if role_id else None
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Constellation HORIZONS terminée : {label}")
                    earned.append(role_name)
                except discord.HTTPException:
                    log.exception("Impossible d'attribuer le rôle de constellation %s", role_name)
    if len(owned) == 20:
        role_name = "🌟 Gardien des 20 étoiles"
        role_id = roles_map.get(role_name)
        role = guild.get_role(int(role_id)) if role_id else None
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Collection des 20 étoiles HORIZONS complétée")
                earned.append(role_name)
            except discord.HTTPException:
                log.exception("Impossible d'attribuer le rôle final des étoiles")
    return earned


async def grant_random_star(guild: discord.Guild, member: discord.Member) -> tuple[str, bool, list[str], bool, int]:
    # Une transaction exclusive protège la collection, la poussière et le
    # compteur de protection contre les séries de doublons.
    stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT star_key FROM celestial_stars WHERE guild_id=? AND user_id=?",
            (guild.id, member.id),
        ).fetchall()
        owned = {row[0] for row in rows}
        progress = conn.execute(
            "SELECT consecutive_duplicates,total_star_draws FROM celestial_star_progress WHERE guild_id=? AND user_id=?",
            (guild.id, member.id),
        ).fetchone()
        streak = int(progress[0]) if progress else 0
        total_draws = int(progress[1]) if progress else 0
        key, protected = choose_star_key(owned, streak)
        is_new = key not in owned
        if is_new:
            conn.execute(
                "INSERT INTO celestial_stars(guild_id,user_id,star_key,obtained_at,source) VALUES(?,?,?,?,?)",
                (guild.id, member.id, key, stamp, "carte"),
            )
            next_streak = 0
        else:
            conn.execute(
                "INSERT INTO celestial_dust(guild_id,user_id,dust) VALUES(?,?,5) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET dust=dust+5",
                (guild.id, member.id),
            )
            next_streak = streak + 1 if len(owned) < len(STARS) else 0
        conn.execute(
            "INSERT INTO celestial_star_progress(guild_id,user_id,consecutive_duplicates,total_star_draws,updated_at) "
            "VALUES(?,?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET "
            "consecutive_duplicates=excluded.consecutive_duplicates,total_star_draws=excluded.total_star_draws,updated_at=excluded.updated_at",
            (guild.id, member.id, next_streak, total_draws + 1, stamp),
        )
        remaining_streak = next_streak
    if is_new:
        sync_collection_unlocks(guild.id, member.id)
    roles = await award_star_roles(guild, member)
    return key, is_new, roles, protected, remaining_streak


def sync_collection_unlocks(guild_id: int, user_id: int) -> list[str]:
    """Enregistre une seule fois les souvenirs correspondant aux étoiles possédées."""
    owned = owned_stars(guild_id, user_id)
    now = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
    unlocked: list[str] = []
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for key, (_label, star_keys, _role) in CONSTELLATIONS.items():
            if set(star_keys).issubset(owned):
                cur = conn.execute(
                    "INSERT OR IGNORE INTO celestial_collection_unlocks(guild_id,user_id,reward_key,unlocked_at) VALUES(?,?,?,?)",
                    (guild_id, user_id, key, now),
                )
                if cur.rowcount:
                    unlocked.append(key)
        if len(owned) == len(STARS):
            cur = conn.execute(
                "INSERT OR IGNORE INTO celestial_collection_unlocks(guild_id,user_id,reward_key,unlocked_at) VALUES(?,?,?,?)",
                (guild_id, user_id, "complete", now),
            )
            if cur.rowcount:
                unlocked.append("complete")
        rows = conn.execute(
            "SELECT reward_key FROM celestial_collection_unlocks WHERE guild_id=? AND user_id=? ORDER BY unlocked_at,reward_key",
            (guild_id, user_id),
        ).fetchall()
    return [row[0] for row in rows]


class ScratchView(discord.ui.View):
    def __init__(self, cog: "CelestialTreasures", owner_id: int):
        super().__init__(timeout=180)
        self.cog, self.owner_id, self.used = cog, owner_id, False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette carte est réservée à la personne qui l'a demandée.", ephemeral=True)
            return False
        if self.used:
            await interaction.response.send_message("Cette carte a déjà été grattée.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✨ Gratter ma carte", style=discord.ButtonStyle.primary)
    async def scratch(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.used = True
        self.stop()
        await self.cog.reveal_card(interaction, self.owner_id)


class CelestialTreasures(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.refresh_treasures_info.start()

    def cog_unload(self):
        self.refresh_treasures_info.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Restaure les rôles célestes correspondant à la collection persistante."""
        try:
            restored = await award_star_roles(member.guild, member)
            if restored:
                log.info(
                    "Rôles célestes restaurés pour %s (%s) : %s",
                    member,
                    member.id,
                    ", ".join(restored),
                )
        except Exception:
            # La collection en base reste intacte : une erreur Discord ne doit
            # jamais empêcher l'arrivée du membre sur le serveur.
            log.exception("Échec de la restauration des rôles célestes pour %s", member.id)

    def build_treasures_embed(self) -> discord.Embed:
        embed = horizons_embed(title="🌌 Les Trésors du Ciel", description="Chaque carte peut révéler une pensée positive, de la poussière céleste, des XP ou l'une des **20 étoiles HORIZONS**. Les doublons deviennent automatiquement de la poussière céleste. Après 12 tirages d'étoile sans nouveauté, le suivant garantit une étoile manquante.")
        embed.add_field(name="✨ Comment participer ?", value="`/gratter` · Une carte quotidienne par jour (heure de Paris). Les cartes offertes sont indépendantes de cette limite.", inline=False)
        embed.add_field(name="🌠 Les 20 étoiles", value="Collectionne les étoiles Aube, Espérance, Courage, Sérénité, Liberté, Écoute, Amitié, Tendresse, Sagesse, Harmonie, Rêve, Confiance, Bienveillance, Résilience, Joie, Mystère, Partage, Unité, Éternité et HORIZONS.", inline=False)
        embed.add_field(name="🌌 Les cinq constellations", value="🌅 Les Origines · 💗 Les Liens · 🔥 Les Forces · ✨ Les Lumières · 🌌 L'Infini\nChaque constellation complète attribue automatiquement son rôle et débloque un souvenir illustré. Les 20 étoiles réunies débloquent le rôle final et le souvenir ultime.", inline=False)
        embed.add_field(name="📜 Tes commandes", value="`/collection_etoiles` · `/constellations` · `/inventaire_celeste` · `/etoile` · `/souvenirs_celestes` · `/echanger_fragments` · `/echanger_poussiere`\n10 fragments donnent une carte offerte ; 20 poussières donnent 1 fragment.", inline=False)
        embed.set_footer(text="HORIZONS • Aucun achat : les cartes sont ludiques et sans valeur monétaire")
        return embed

    @tasks.loop(hours=2)
    async def refresh_treasures_info(self):
        for guild in self.bot.guilds:
            channel_id = get_ludic_setting(guild.id, "treasures_channel_id")
            if not channel_id:
                continue
            channel = guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                continue
            message_id = get_ludic_setting(guild.id, "treasures_info_message_id")
            # Republier le panneau pour qu'il reste visible après les échanges.
            # Aucun message des membres n'est touché.
            try:
                if message_id:
                    try:
                        old_message = await channel.fetch_message(int(message_id))
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                        pass
                message = await channel.send(embed=self.build_treasures_embed())
                with db() as conn:
                    conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"ludic:{guild.id}:treasures_info_message_id", json.dumps(message.id)))
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Impossible de republier le panneau Trésors du Ciel.")

    @refresh_treasures_info.before_loop
    async def before_refresh_treasures_info(self):
        await self.bot.wait_until_ready()

    async def require_treasures_channel(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild_id:
            await interaction.response.send_message("Cette commande est disponible sur le serveur HORIZONS.", ephemeral=True)
            return False
        channel_id = get_ludic_setting(interaction.guild_id, "treasures_channel_id")
        if not channel_id:
            await interaction.response.send_message("L'espace Trésors du Ciel n'est pas encore créé. L'équipe doit lancer `/ajoutstructure`.", ephemeral=True)
            return False
        if interaction.channel_id != int(channel_id):
            channel = interaction.guild.get_channel(int(channel_id)) if interaction.guild else None
            await interaction.response.send_message(f"Cette commande se joue dans {channel.mention if channel else 'le salon Trésors du Ciel'} !", ephemeral=True)
            return False
        return True

    async def reveal_card(self, interaction: discord.Interaction, user_id: int):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Cette carte doit être utilisée sur HORIZONS.", ephemeral=True)
            return
        member = interaction.user
        day = today_key()
        stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        source = None
        card_id = None
        with db() as conn:
            # Une seule ouverture quotidienne même si plusieurs boutons /gratter
            # sont utilisés simultanément par le même membre.
            conn.execute("BEGIN IMMEDIATE")
            daily = conn.execute("SELECT id FROM celestial_daily_cards WHERE guild_id=? AND user_id=? AND card_date=? AND used_at IS NOT NULL", (guild.id,user_id,day)).fetchone()
            if not daily:
                cur = conn.execute("INSERT INTO celestial_daily_cards(guild_id,user_id,card_date,used_at) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id,card_date) DO UPDATE SET used_at=excluded.used_at", (guild.id,user_id,day,stamp))
                source = "daily"
            else:
                gift = conn.execute("SELECT id FROM celestial_gift_cards WHERE guild_id=? AND user_id=? AND used_at IS NULL ORDER BY id LIMIT 1", (guild.id,user_id)).fetchone()
                if not gift:
                    await interaction.response.send_message("Tu as déjà utilisé ta carte du jour et tu n'as plus de carte offerte disponible.", ephemeral=True)
                    return
                card_id = int(gift[0])
                conn.execute("UPDATE celestial_gift_cards SET used_at=? WHERE id=? AND used_at IS NULL", (stamp,card_id))
                source = "gift"
        # Probabilités pondérées, conservées et contrôlées à 100 %.
        reward = random.choices(list(REWARD_WEIGHTS), weights=list(REWARD_WEIGHTS.values()), k=1)[0]
        title = "✨ Une petite lumière pour toi"
        details = ""
        if reward == "thought":
            details = random.choice(POSITIVE_THOUGHTS)
        elif reward == "dust":
            amount = random.randint(3,8); balance = add_dust(guild.id,user_id,amount)
            details = f"Tu remportes **{amount} poussières célestes**. Ton total : **{balance}**."
        elif reward == "xp":
            amount = random.randint(5,15)
            points = award_xp(guild.id,user_id,f"carte:{source}:{card_id or day}",amount)
            xp = total_xp(guild.id,user_id); level,name = xp_level(xp)
            details = f"**+{points} XP Célestes** ! Tu disposes maintenant de **{xp} XP**, niveau **{level} — {name}**."
        elif reward == "star":
            star_key, new, roles, protected, streak = await grant_random_star(guild,member)
            star = STARS[star_key]
            if new:
                details = f"Tu découvres l'étoile **{star[0]}** {star[3]} — *{star[1]}*.\\n{star[2]}"
                if protected:
                    details += "\\n\\n🛡️ **Protection céleste activée :** cette étoile manquante t'est garantie après 12 tirages sans nouveauté."
                if roles: details += "\\n\\nRôle(s) débloqué(s) : " + ", ".join(roles)
                title = f"🌟 Nouvelle étoile : {star[0]}"
            else:
                details = f"L'étoile **{star[0]}** était déjà dans ta collection : elle se transforme en **5 poussières célestes**. Ton total : **{dust_balance(guild.id,user_id)}**."
                details += f"\\nProgression de la protection : **{streak}/{STAR_PITY_LIMIT}** tirages d'étoile sans nouveauté."
                title = "🌠 Un doublon devenu poussière céleste"
        elif reward == "fragment":
            amount = random.randint(1,3)
            with db() as conn:
                conn.execute("INSERT INTO celestial_fragments(guild_id,user_id,fragments) VALUES(?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET fragments=fragments+excluded.fragments", (guild.id,user_id,amount))
                total = conn.execute("SELECT fragments FROM celestial_fragments WHERE guild_id=? AND user_id=?", (guild.id,user_id)).fetchone()[0]
            details = f"Tu remportes **{amount} fragments de constellation**. Tu en possèdes **{total}**."
        else:
            amount = 25; balance = add_dust(guild.id,user_id,amount)
            details = f"Une belle surprise ! **+25 poussières célestes**. Ton total : **{balance}**."
            title = "🎁 Une surprise céleste !"
        embed = horizons_embed(title=title, description=details)
        embed.set_thumbnail(url="attachment://carte_celeste.png")
        embed.set_image(url=f"attachment://{reward}.png")
        embed.add_field(name="Carte utilisée", value="Carte quotidienne" if source == "daily" else "Carte offerte", inline=True)
        embed.set_footer(text="HORIZONS • Chaque étoile raconte quelque chose")
        files = [discord.File(CARD_ART, filename="carte_celeste.png"), discord.File(REWARD_ART[reward], filename=f"{reward}.png")]
        await interaction.response.edit_message(content=None, embed=embed, attachments=files, view=None)

    @app_commands.command(name="gratter", description="Gratter ta carte quotidienne ou une carte offerte.")
    async def gratter(self, interaction: discord.Interaction):
        if not await self.require_treasures_channel(interaction):
            return
        missing_assets = [path.name for path in [CARD_ART, *REWARD_ART.values()] if not path.is_file()]
        if missing_assets:
            log.error("Visuels des cartes célestes manquants : %s", ", ".join(missing_assets))
            await interaction.response.send_message("Les visuels des cartes ne sont pas tous disponibles. Préviens l'équipe avant de réessayer.", ephemeral=True)
            return
        day = today_key()
        with db() as conn:
            used = conn.execute("SELECT 1 FROM celestial_daily_cards WHERE guild_id=? AND user_id=? AND card_date=? AND used_at IS NOT NULL", (interaction.guild_id,interaction.user.id,day)).fetchone()
            gift = conn.execute("SELECT 1 FROM celestial_gift_cards WHERE guild_id=? AND user_id=? AND used_at IS NULL LIMIT 1", (interaction.guild_id,interaction.user.id)).fetchone()
        if used and not gift:
            await interaction.response.send_message("Tu as déjà gratté ta carte du jour. Reviens demain pour une nouvelle surprise ! 🌠", ephemeral=True)
            return
        embed = horizons_embed(title="🎟️ Ta carte céleste", description="Une surprise t'attend. Clique sur le bouton pour découvrir ce que le ciel t'a réservé !")
        embed.set_image(url="attachment://carte_celeste.png")
        embed.set_footer(text="Une carte quotidienne • Les cartes offertes sont indépendantes")
        await interaction.response.send_message(embed=embed, file=discord.File(CARD_ART, filename="carte_celeste.png"), view=ScratchView(self,interaction.user.id), ephemeral=True)

    @app_commands.command(name="givegratte", description="Offrir des cartes à gratter à un membre (administration).")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(membre="Membre qui recevra les cartes", quantite="Nombre de cartes offertes", raison="Motif du cadeau")
    async def givegratte(self, interaction: discord.Interaction, membre: discord.Member, quantite: app_commands.Range[int,1,100], raison: str):
        if not raison.strip():
            await interaction.response.send_message("Merci d'indiquer une raison.", ephemeral=True)
            return
        stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        with db() as conn:
            for _ in range(quantite):
                conn.execute("INSERT INTO celestial_gift_cards(guild_id,user_id,granted_by,reason,created_at) VALUES(?,?,?,?,?)", (interaction.guild_id,membre.id,interaction.user.id,raison[:300],stamp))
            conn.execute("INSERT INTO celestial_gift_history(guild_id,recipient_id,giver_id,quantity,reason,created_at) VALUES(?,?,?,?,?,?)", (interaction.guild_id,membre.id,interaction.user.id,quantite,raison[:300],stamp))
        await interaction.response.send_message(f"🎁 **{quantite} carte(s)** offerte(s) à {membre.mention}.\nMotif : {raison[:300]}", ephemeral=True)

    @app_commands.command(name="echanger_fragments", description="Échanger 10 fragments contre une carte à gratter offerte.")
    @app_commands.guild_only()
    async def echanger_fragments(self, interaction: discord.Interaction):
        if not await self.require_treasures_channel(interaction):
            return
        stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        # Débit des fragments et création de la carte dans une seule
        # transaction : aucun échange partiel en cas de double clic.
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT fragments FROM celestial_fragments WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()
            balance = int(row[0]) if row else 0
            if balance < 10:
                await interaction.response.send_message(
                    f"Il te manque **{10 - balance} fragment(s)** pour obtenir une carte offerte. Tu en possèdes {balance}/10.",
                    ephemeral=True,
                )
                return
            conn.execute(
                "UPDATE celestial_fragments SET fragments=fragments-10 WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            )
            conn.execute(
                "INSERT INTO celestial_gift_cards(guild_id,user_id,granted_by,reason,created_at) VALUES(?,?,?,?,?)",
                (interaction.guild_id, interaction.user.id, interaction.user.id,
                 "Échange de 10 fragments de constellation", stamp),
            )
            remaining = balance - 10
        await interaction.response.send_message(
            f"💠 Échange réussi ! 10 fragments ont été utilisés.\n🎟️ Une carte offerte a été ajoutée à ton inventaire.\nIl te reste **{remaining} fragment(s)**. Utilise `/gratter` pour la découvrir !",
            ephemeral=True,
        )

    @app_commands.command(name="echanger_poussiere", description="Échanger 20 poussières célestes contre 1 fragment de constellation.")
    @app_commands.guild_only()
    async def echanger_poussiere(self, interaction: discord.Interaction):
        if not await self.require_treasures_channel(interaction):
            return
        stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT dust FROM celestial_dust WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()
            balance = int(row[0]) if row else 0
            if balance < 20:
                await interaction.response.send_message(
                    f"Il te manque **{20 - balance} poussière(s)**. Tu en possèdes {balance}/20.",
                    ephemeral=True,
                )
                return
            conn.execute(
                "UPDATE celestial_dust SET dust=dust-20 WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            )
            conn.execute(
                "INSERT INTO celestial_fragments(guild_id,user_id,fragments) VALUES(?,?,1) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET fragments=fragments+1",
                (interaction.guild_id, interaction.user.id),
            )
            remaining = balance - 20
            frag_row = conn.execute(
                "SELECT fragments FROM celestial_fragments WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()
            fragments = int(frag_row[0])
        await interaction.response.send_message(
            f"✨ Échange réussi : 20 poussières célestes ont été converties en **1 fragment**.\n"
            f"Il te reste **{remaining} poussière(s)** et tu possèdes maintenant **{fragments} fragment(s)**.",
            ephemeral=True,
        )

    @app_commands.command(name="collection_etoiles", description="Consulter ta collection personnelle des 20 étoiles.")
    async def collection_etoiles(self, interaction: discord.Interaction):
        if not interaction.guild_id: return await interaction.response.send_message("Commande disponible sur HORIZONS.",ephemeral=True)
        owned = owned_stars(interaction.guild_id,interaction.user.id)
        lines = []
        for key,(name,meaning,story,emoji) in STARS.items():
            lines.append(f"{'🌟' if key in owned else '🔒'} {emoji} **{name}** — {meaning}")
        embed = horizons_embed(title=f"🌠 Collection de {interaction.user.display_name}", description="\n".join(lines))
        embed.add_field(name="Progression", value=f"**{len(owned)}/20 étoiles** découvertes")
        await interaction.response.send_message(embed=embed,ephemeral=True)

    @app_commands.command(name="constellations", description="Voir les constellations et leurs étoiles à réunir.")
    async def constellations(self, interaction: discord.Interaction):
        if not interaction.guild_id: return await interaction.response.send_message("Commande disponible sur HORIZONS.",ephemeral=True)
        owned = owned_stars(interaction.guild_id,interaction.user.id)
        embed = horizons_embed(title="🌌 Les cinq constellations HORIZONS", description="Réunis les quatre étoiles de chaque constellation pour débloquer automatiquement son rôle.")
        for label,keys,role in CONSTELLATIONS.values():
            found = sum(key in owned for key in keys)
            names = " · ".join(STARS[key][0] for key in keys)
            embed.add_field(name=f"{label} — {found}/4", value=f"{names}\nRôle : **{role}**", inline=False)
        embed.add_field(name="🌟 Collection complète", value=f"{len(owned)}/20 étoiles · rôle final **Gardien des 20 étoiles**")
        await interaction.response.send_message(embed=embed,ephemeral=True)

    @app_commands.command(name="inventaire_celeste", description="Consulter tes poussières, fragments, cartes offertes et XP.")
    async def inventaire_celeste(self, interaction: discord.Interaction):
        if not interaction.guild_id: return await interaction.response.send_message("Commande disponible sur HORIZONS.",ephemeral=True)
        with db() as conn:
            frag = conn.execute("SELECT fragments FROM celestial_fragments WHERE guild_id=? AND user_id=?", (interaction.guild_id,interaction.user.id)).fetchone()
            gifts = conn.execute("SELECT COUNT(*) FROM celestial_gift_cards WHERE guild_id=? AND user_id=? AND used_at IS NULL", (interaction.guild_id,interaction.user.id)).fetchone()[0]
        xp = total_xp(interaction.guild_id,interaction.user.id)
        with db() as conn:
            pity = conn.execute("SELECT consecutive_duplicates FROM celestial_star_progress WHERE guild_id=? AND user_id=?", (interaction.guild_id,interaction.user.id)).fetchone()
        streak = int(pity[0]) if pity else 0
        embed = horizons_embed(title="🎒 Ton inventaire céleste", description=f"🌟 **XP Célestes :** {xp}\n✨ **Poussières célestes :** {dust_balance(interaction.guild_id,interaction.user.id)}\n💠 **Fragments de constellation :** {int(frag[0]) if frag else 0}\n🎟️ **Cartes offertes disponibles :** {gifts}\n🌠 **Étoiles découvertes :** {len(owned_stars(interaction.guild_id,interaction.user.id))}/20\n🛡️ **Protection des étoiles :** {streak}/{STAR_PITY_LIMIT}")
        embed.add_field(name="💱 Échanges disponibles", value="20 poussières = 1 fragment · 10 fragments = 1 carte offerte", inline=False)
        await interaction.response.send_message(embed=embed,ephemeral=True)

    @app_commands.command(name="souvenirs_celestes", description="Retrouver les souvenirs illustrés débloqués par ta collection.")
    async def souvenirs_celestes(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("Commande disponible sur HORIZONS.", ephemeral=True)
            return
        keys = sync_collection_unlocks(interaction.guild_id, interaction.user.id)
        if not keys:
            await interaction.response.send_message(
                "Aucun souvenir débloqué pour le moment. Réunis les quatre étoiles d'une constellation pour découvrir son histoire illustrée ! 🌠",
                ephemeral=True,
            )
            return
        embeds = []
        files = []
        for key in keys:
            title, story, filename = COLLECTION_REWARDS[key]
            path = ASSETS / filename
            if not path.is_file():
                log.error("Illustration de souvenir manquante : %s", filename)
                continue
            embed = horizons_embed(title=title, description=story)
            embed.set_image(url=f"attachment://{filename}")
            embed.set_footer(text="HORIZONS • Souvenir de collection débloqué")
            embeds.append(embed)
            files.append(discord.File(path, filename=filename))
        if not embeds:
            await interaction.response.send_message("Les illustrations des souvenirs sont momentanément indisponibles. Préviens l'équipe.", ephemeral=True)
            return
        await interaction.response.send_message(embeds=embeds, files=files, ephemeral=True)

    @app_commands.command(name="etoile", description="Découvrir la signification d'une étoile HORIZONS.")
    @app_commands.choices(nom=[app_commands.Choice(name=data[0],value=key) for key,data in STARS.items()])
    async def etoile(self, interaction: discord.Interaction, nom: app_commands.Choice[str]):
        data = STARS[nom.value]
        embed = horizons_embed(title=f"{data[3]} {data[0]}", description=f"**{data[1]}**\n\n{data[2]}")
        if interaction.guild_id and nom.value in owned_stars(interaction.guild_id,interaction.user.id):
            embed.add_field(name="Ta collection", value="Tu possèdes déjà cette étoile. 🌟")
        await interaction.response.send_message(embed=embed,ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CelestialTreasures(bot))
