"""Historique, statistiques et succès de progression des jeux HORIZONS."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from config import LOCAL_TIMEZONE
from cogs.storage import db

ACHIEVEMENTS = {
    "premiere_partie": ("🌱 Premier pas", "Terminer ta première partie."),
    "premiere_victoire": ("🏆 Première victoire", "Remporter ta première partie."),
    "joueur_regulier": ("🎮 Joueur régulier", "Terminer dix parties."),
    "champion": ("👑 Champion", "Remporter dix parties."),
    "explorateur": ("🧭 Explorateur", "Jouer à trois jeux différents."),
    "polyvalent": ("🌈 Polyvalent", "Jouer aux six jeux de l'Arcade."),
    "morpion_5": ("⭕ Stratège du Morpion", "Remporter cinq parties de Morpion."),
    "puissance4_5": ("🔴 Alignement parfait", "Remporter cinq parties de Puissance 4."),
    "memory_5": ("🧠 Mémoire d'or", "Terminer cinq parties de Memory."),
    "code_secret_5": ("🔐 Décrypteur", "Découvrir cinq codes secrets."),
    "petit_bac_5": ("📝 Plume rapide", "Remporter cinq manches de Petit Bac."),
    "bataille_navale_5": ("🚢 Amiral", "Remporter cinq batailles navales."),
}


WEEKLY_MISSIONS = {
    "parties_3": {"title": "Faire trois parties", "description": "Terminer trois parties de l'Arcade.", "target": 3, "reward": 15},
    "victories_2": {"title": "Décrocher deux victoires", "description": "Remporter deux parties.", "target": 2, "reward": 20},
    "variety_3": {"title": "Explorer trois jeux", "description": "Jouer à trois jeux différents.", "target": 3, "reward": 20},
    "duel_1": {"title": "Oser le duel", "description": "Participer à un duel contre un membre.", "target": 1, "reward": 15},
    "collective_1": {"title": "Jouer ensemble", "description": "Participer à une partie collective.", "target": 1, "reward": 15},
}


def current_week_key(now: datetime | None = None) -> str:
    moment = now or datetime.now(LOCAL_TIMEZONE)
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _week_start(week_key: str) -> str:
    year_text, week_text = week_key.split("-W", 1)
    monday = datetime.fromisocalendar(int(year_text), int(week_text), 1)
    monday = monday.replace(tzinfo=LOCAL_TIMEZONE)
    return monday.isoformat(timespec="seconds")


def _ensure_weekly_missions(conn, guild_id: int, user_id: int, week_key: str) -> None:
    for mission_key in WEEKLY_MISSIONS:
        conn.execute(
            "INSERT OR IGNORE INTO celestial_weekly_missions(guild_id,user_id,week_key,mission_key) VALUES(?,?,?,?)",
            (guild_id, user_id, week_key, mission_key),
        )


def _refresh_weekly_missions(conn, guild_id: int, user_id: int, week_key: str, stamp: str) -> None:
    _ensure_weekly_missions(conn, guild_id, user_id, week_key)
    start_stamp = _week_start(week_key)
    rows = conn.execute(
        """SELECT game_key,mode,players_json,winners_json,status
           FROM celestial_game_history h
           WHERE guild_id=? AND ended_at>=? AND status IN ('completed','draw','loss')
             AND EXISTS (SELECT 1 FROM json_each(h.players_json) p WHERE CAST(p.value AS INTEGER)=?)
           ORDER BY ended_at ASC""",
        (guild_id, start_stamp, user_id),
    ).fetchall()
    played = len(rows)
    wins = sum(user_id in json.loads(row["winners_json"]) for row in rows)
    distinct_games = len({row["game_key"] for row in rows})
    duels = sum(row["mode"] == "duel" and len(json.loads(row["players_json"])) >= 2 for row in rows)
    collective = sum(row["mode"] == "collectif" for row in rows)
    values = {
        "parties_3": played,
        "victories_2": wins,
        "variety_3": distinct_games,
        "duel_1": duels,
        "collective_1": collective,
    }
    for mission_key, progress in values.items():
        target = WEEKLY_MISSIONS[mission_key]["target"]
        conn.execute(
            """UPDATE celestial_weekly_missions
               SET progress=?, completed_at=CASE WHEN ? >= ? THEN COALESCE(completed_at,?) ELSE completed_at END
               WHERE guild_id=? AND user_id=? AND week_key=? AND mission_key=?""",
            (progress, progress, target, stamp, guild_id, user_id, week_key, mission_key),
        )


def record_game_result(
    guild_id: int,
    game_key: str,
    mode: str,
    players: list[int] | tuple[int, ...],
    winners: list[int] | tuple[int, ...] = (),
    status: str = "completed",
    scores: dict[int, int] | None = None,
    started_at: str | None = None,
) -> list[str]:
    """Enregistre une partie terminée et retourne les succès nouvellement débloqués."""
    player_ids = list(dict.fromkeys(int(user_id) for user_id in players))
    winner_ids = list(dict.fromkeys(int(user_id) for user_id in winners if int(user_id) in player_ids))
    if not player_ids:
        return []
    now = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
    start_stamp = started_at or now
    session_id = uuid.uuid4().hex
    score_map = {str(int(user_id)): int(score) for user_id, score in (scores or {}).items() if int(user_id) in player_ids}
    newly_unlocked: dict[int, list[str]] = {user_id: [] for user_id in player_ids}

    with db() as conn:
        conn.execute(
            """INSERT INTO celestial_game_history
               (session_id,guild_id,game_key,mode,players_json,winners_json,status,scores_json,started_at,ended_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, guild_id, game_key, mode,
                json.dumps(player_ids), json.dumps(winner_ids), status,
                json.dumps(score_map), start_stamp, now,
            ),
        )
        for user_id in player_ids:
            won = user_id in winner_ids
            lost = (bool(winner_ids) and not won) or status == "loss"
            draw = status == "draw"
            conn.execute(
                """INSERT INTO celestial_game_player_stats
                   (guild_id,user_id,game_key,played,wins,losses,draws,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(guild_id,user_id,game_key) DO UPDATE SET
                     played=played+1,
                     wins=wins+excluded.wins,
                     losses=losses+excluded.losses,
                     draws=draws+excluded.draws,
                     updated_at=excluded.updated_at""",
                (guild_id, user_id, game_key, 1, int(won), int(lost), int(draw), now),
            )

        for user_id in player_ids:
            total = conn.execute(
                "SELECT COALESCE(SUM(played),0), COALESCE(SUM(wins),0) FROM celestial_game_player_stats WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            ).fetchone()
            total_played, total_wins = int(total[0]), int(total[1])
            total_completed = conn.execute(
                """SELECT COUNT(*) FROM celestial_game_history h
                   WHERE guild_id=? AND status IN ('completed','draw','loss')
                     AND EXISTS (SELECT 1 FROM json_each(h.players_json) p WHERE CAST(p.value AS INTEGER)=?)""",
                (guild_id, user_id),
            ).fetchone()[0]
            distinct_games = conn.execute(
                """SELECT COUNT(DISTINCT game_key) FROM celestial_game_history h
                   WHERE guild_id=? AND status IN ('completed','draw','loss')
                     AND EXISTS (SELECT 1 FROM json_each(h.players_json) p WHERE CAST(p.value AS INTEGER)=?)""",
                (guild_id, user_id),
            ).fetchone()[0]
            game_wins = conn.execute(
                "SELECT wins FROM celestial_game_player_stats WHERE guild_id=? AND user_id=? AND game_key=?",
                (guild_id, user_id, game_key),
            ).fetchone()
            this_game_wins = int(game_wins[0]) if game_wins else 0
            conditions = {
                "premiere_partie": total_completed >= 1,
                "premiere_victoire": total_wins >= 1,
                "joueur_regulier": total_completed >= 10,
                "champion": total_wins >= 10,
                "explorateur": int(distinct_games) >= 3,
                "polyvalent": int(distinct_games) >= 6,
                "morpion_5": game_key == "morpion" and this_game_wins >= 5,
                "puissance4_5": game_key == "puissance4" and this_game_wins >= 5,
                "memory_5": game_key == "memory" and this_game_wins >= 5,
                "code_secret_5": game_key == "code_secret" and this_game_wins >= 5,
                "petit_bac_5": game_key == "petit_bac" and this_game_wins >= 5,
                "bataille_navale_5": game_key == "bataille_navale" and this_game_wins >= 5,
            }
            for achievement_key, unlocked in conditions.items():
                if not unlocked:
                    continue
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO celestial_game_achievements(guild_id,user_id,achievement_key,unlocked_at) VALUES(?,?,?,?)",
                    (guild_id, user_id, achievement_key, now),
                )
                if cursor.rowcount:
                    newly_unlocked[user_id].append(achievement_key)
            _refresh_weekly_missions(conn, guild_id, user_id, current_week_key(), now)

    # Le retour global est utile pour les annonces et les tests ; les clés restent
    # uniques, même si plusieurs joueurs débloquent le même succès simultanément.
    return sorted({key for keys in newly_unlocked.values() for key in keys})


def get_game_stats(guild_id: int, user_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT game_key,played,wins,losses,draws
               FROM celestial_game_player_stats
               WHERE guild_id=? AND user_id=? AND played>0
               ORDER BY played DESC, game_key ASC""",
            (guild_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_game_history(guild_id: int, user_id: int, limit: int = 8) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT session_id,game_key,mode,players_json,winners_json,status,scores_json,ended_at
               FROM celestial_game_history h
               WHERE guild_id=? AND EXISTS (
                 SELECT 1 FROM json_each(h.players_json) AS player WHERE CAST(player.value AS INTEGER)=?
               )
               ORDER BY ended_at DESC LIMIT ?""",
            (guild_id, int(user_id), max(1, min(20, int(limit)))),
        ).fetchall()
    result = []
    for row in rows:
        try:
            players = json.loads(row["players_json"])
            if user_id not in players:
                continue
            result.append({
                "session_id": row["session_id"],
                "game_key": row["game_key"],
                "mode": row["mode"],
                "players": players,
                "winners": json.loads(row["winners_json"]),
                "status": row["status"],
                "scores": json.loads(row["scores_json"]),
                "ended_at": row["ended_at"],
            })
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return result


def get_achievements(guild_id: int, user_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT achievement_key,unlocked_at FROM celestial_game_achievements WHERE guild_id=? AND user_id=? ORDER BY unlocked_at DESC",
            (guild_id, user_id),
        ).fetchall()
    result = []
    for row in rows:
        title, description = ACHIEVEMENTS.get(row["achievement_key"], (row["achievement_key"], "Succès débloqué."))
        result.append({"key": row["achievement_key"], "title": title, "description": description, "unlocked_at": row["unlocked_at"]})
    return result


def get_weekly_missions(guild_id: int, user_id: int, week_key: str | None = None) -> list[dict]:
    week = week_key or current_week_key()
    stamp = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
    with db() as conn:
        _refresh_weekly_missions(conn, guild_id, user_id, week, stamp)
        rows = conn.execute(
            "SELECT mission_key,progress,completed_at,claimed_at,xp_awarded FROM celestial_weekly_missions WHERE guild_id=? AND user_id=? AND week_key=? ORDER BY mission_key",
            (guild_id, user_id, week),
        ).fetchall()
    result = []
    for row in rows:
        definition = WEEKLY_MISSIONS[row["mission_key"]]
        result.append({"key": row["mission_key"], **definition, "progress": int(row["progress"]), "completed_at": row["completed_at"], "claimed_at": row["claimed_at"], "xp_awarded": int(row["xp_awarded"]), "week_key": week})
    return result


def get_pending_weekly_missions(guild_id: int, user_id: int) -> list[dict]:
    """Récompenses terminées mais non réclamées, y compris les semaines passées."""
    with db() as conn:
        rows = conn.execute(
            """SELECT week_key,mission_key,progress,completed_at,claimed_at,xp_awarded
               FROM celestial_weekly_missions
               WHERE guild_id=? AND user_id=? AND completed_at IS NOT NULL AND claimed_at IS NULL
               ORDER BY week_key DESC, mission_key ASC""",
            (guild_id, user_id),
        ).fetchall()
    result = []
    for row in rows:
        definition = WEEKLY_MISSIONS[row["mission_key"]]
        result.append({"key": row["mission_key"], **definition, "progress": int(row["progress"]), "completed_at": row["completed_at"], "claimed_at": row["claimed_at"], "xp_awarded": int(row["xp_awarded"]), "week_key": row["week_key"]})
    return result


def claim_weekly_mission(guild_id: int, user_id: int, week_key: str, mission_key: str) -> int:
    definition = WEEKLY_MISSIONS.get(mission_key)
    if not definition:
        return 0
    now = datetime.now(LOCAL_TIMEZONE)
    stamp = now.isoformat(timespec="seconds")
    day = now.date().isoformat()
    reward_key = f"mission:{week_key}:{mission_key}"
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT completed_at,claimed_at FROM celestial_weekly_missions WHERE guild_id=? AND user_id=? AND week_key=? AND mission_key=?",
            (guild_id, user_id, week_key, mission_key),
        ).fetchone()
        if not row or not row["completed_at"] or row["claimed_at"]:
            return 0
        if conn.execute(
            "SELECT 1 FROM celestial_game_rewards WHERE guild_id=? AND user_id=? AND reward_date=? AND game_key=?",
            (guild_id, user_id, day, reward_key),
        ).fetchone():
            return 0
        daily_total = conn.execute(
            "SELECT COALESCE(SUM(xp_awarded),0) FROM celestial_game_rewards WHERE guild_id=? AND user_id=? AND reward_date=?",
            (guild_id, user_id, day),
        ).fetchone()[0]
        awarded = max(0, min(int(definition["reward"]), 60 - int(daily_total)))
        if awarded <= 0:
            return 0
        conn.execute(
            "INSERT INTO celestial_game_rewards(guild_id,user_id,reward_date,game_key,xp_awarded,created_at) VALUES(?,?,?,?,?,?)",
            (guild_id, user_id, day, reward_key, awarded, stamp),
        )
        conn.execute(
            "INSERT INTO celestial_game_xp(guild_id,user_id,xp,updated_at) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=xp+excluded.xp,updated_at=excluded.updated_at",
            (guild_id, user_id, awarded, stamp),
        )
        conn.execute(
            "UPDATE celestial_weekly_missions SET claimed_at=?,xp_awarded=? WHERE guild_id=? AND user_id=? AND week_key=? AND mission_key=?",
            (stamp, awarded, guild_id, user_id, week_key, mission_key),
        )
        return awarded


def claim_all_weekly_missions(guild_id: int, user_id: int) -> tuple[int, int]:
    missions = get_pending_weekly_missions(guild_id, user_id)
    total = count = 0
    for mission in missions:
        points = claim_weekly_mission(guild_id, user_id, mission["week_key"], mission["key"])
        if points:
            total += points
            count += 1
    return total, count


# ---------------------------------------------------------------------------
# Interface privée /xpjeux : aperçu, statistiques, historique et succès
# ---------------------------------------------------------------------------

import discord
from cogs.embed_theme import horizons_embed

GAME_LABELS = {
    "de": "🎲 Dé",
    "pileface": "🪙 Pile ou face",
    "nombre_mystere": "🔢 Nombre mystère",
    "quizjeu": "🧠 Quiz de l'Arcade",
    "anagramme": "🔤 Anagramme",
    "enigme": "🧩 Énigme",
    "reflexe": "⚡ Réflexe",
    "morpion": "⭕ Morpion",
    "puissance4": "🔴 Puissance 4",
    "memory": "🧠 Memory",
    "code_secret": "🔐 Code secret",
    "petit_bac": "📝 Petit Bac",
    "bataille_navale": "🚢 Bataille navale",
    "arcade_night": "🌠 Soirée Arcade",
}


class ProgressView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, xp: int, level: int, level_title: str):
        super().__init__(timeout=180)
        self.guild_id, self.user_id = guild_id, user_id
        self.xp, self.level, self.level_title = xp, level, level_title

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce passeport céleste est privé.", ephemeral=True)
            return False
        return True

    def overview_embed(self) -> discord.Embed:
        stats = get_game_stats(self.guild_id, self.user_id)
        achievements = get_achievements(self.guild_id, self.user_id)
        played = sum(item["played"] for item in stats)
        wins = sum(item["wins"] for item in stats)
        next_xp = self.level * 50
        return horizons_embed(
            title="🌟 Ton passeport céleste",
            description=(
                f"**{self.xp} XP Célestes**\nNiveau **{self.level} — {self.level_title}**\n"
                f"Encore **{max(0, next_xp - self.xp)} XP** pour le prochain niveau.\n\n"
                f"Parties suivies : **{played}** · Victoires : **{wins}**\n"
                f"Succès débloqués : **{len(achievements)}/{len(ACHIEVEMENTS)}**"
            ),
        )

    def stats_embed(self) -> discord.Embed:
        stats = get_game_stats(self.guild_id, self.user_id)
        embed = horizons_embed(title="📊 Tes statistiques Arcade")
        if not stats:
            embed.description = "Tes statistiques apparaîtront après ta première partie terminée."
            return embed
        lines = []
        for item in stats:
            played, wins = item["played"], item["wins"]
            rate = round((wins / played) * 100) if played else 0
            label = GAME_LABELS.get(item["game_key"], item["game_key"])
            lines.append(
                f"**{label}** — {played} partie(s)\n"
                f"🏆 {wins} victoire(s) · {item['losses']} défaite(s) · {item['draws']} nul(s) · {rate}% de victoires"
            )
        embed.description = "\n\n".join(lines[:10])
        return embed

    def history_embed(self) -> discord.Embed:
        history = get_game_history(self.guild_id, self.user_id, 8)
        embed = horizons_embed(title="📜 Ton historique récent")
        if not history:
            embed.description = "Aucune partie terminée n'est encore enregistrée."
            return embed
        lines = []
        for item in history:
            label = GAME_LABELS.get(item["game_key"], item["game_key"])
            winners = item["winners"]
            if item["status"] == "draw":
                result = "Match nul"
            elif item["status"] == "timeout":
                result = "Arrêt pour inactivité"
            elif item["status"] == "abandoned":
                result = "Abandon"
            elif self.user_id in winners:
                result = "Victoire"
            elif winners or item["status"] == "loss":
                result = "Défaite"
            else:
                result = "Partie terminée"
            try:
                date = datetime.fromisoformat(item["ended_at"]).strftime("%d/%m/%Y à %H:%M")
            except (TypeError, ValueError):
                date = item["ended_at"]
            opponents = [f"<@{uid}>" for uid in item["players"] if uid != self.user_id]
            versus = f" contre {', '.join(opponents)}" if opponents else " en solo"
            lines.append(f"**{label}**{versus}\n{date} · **{result}**")
        embed.description = "\n\n".join(lines)
        return embed

    def missions_embed(self) -> discord.Embed:
        missions = get_weekly_missions(self.guild_id, self.user_id)
        week = missions[0]["week_key"] if missions else current_week_key()
        lines = []
        for mission in missions:
            if mission["claimed_at"]:
                status = f"🎁 Récompense récupérée : +{mission['xp_awarded']} XP"
            elif mission["completed_at"]:
                status = "✅ Mission terminée — récompense disponible"
            else:
                status = f"Progression : **{mission['progress']}/{mission['target']}**"
            lines.append(
                f"**{mission['title']}** — {mission['description']}\n"
                f"{status} · Récompense : **{mission['reward']} XP**"
            )
        pending = get_pending_weekly_missions(self.guild_id, self.user_id)
        previous = [mission for mission in pending if mission["week_key"] != week]
        if previous:
            lines.append("**Récompenses en attente des semaines précédentes :**")
            lines.extend(f"• {mission['title']} ({mission['week_key']}) — **+{mission['reward']} XP**" for mission in previous[:5])
        embed = horizons_embed(title="🗓️ Tes missions hebdomadaires", description="\n\n".join(lines) if lines else "Aucune mission n'est disponible cette semaine.")
        embed.set_footer(text=f"Semaine {week} • Les récompenses respectent le plafond quotidien de 60 XP")
        return embed

    def achievements_embed(self) -> discord.Embed:
        unlocked = get_achievements(self.guild_id, self.user_id)
        embed = horizons_embed(title="🏅 Tes succès et badges")
        if not unlocked:
            embed.description = f"Aucun badge débloqué pour le moment. Il y a **{len(ACHIEVEMENTS)} succès** à découvrir dans l'Arcade."
            return embed
        embed.description = f"**{len(unlocked)}/{len(ACHIEVEMENTS)} succès débloqués**\n\n" + "\n\n".join(
            f"**{item['title']}**\n{item['description']}"
            for item in unlocked[:12]
        )
        return embed

    @discord.ui.button(label="Statistiques", style=discord.ButtonStyle.primary, emoji="📊", row=0)
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.stats_embed(), view=self)

    @discord.ui.button(label="Historique", style=discord.ButtonStyle.secondary, emoji="📜", row=0)
    async def show_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.history_embed(), view=self)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, emoji="🏅", row=0)
    async def show_achievements(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.achievements_embed(), view=self)

    @discord.ui.button(label="Vue d'ensemble", style=discord.ButtonStyle.secondary, emoji="🌟", row=1)
    async def show_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.overview_embed(), view=self)

    @discord.ui.button(label="Missions", style=discord.ButtonStyle.primary, emoji="🗓️", row=1)
    async def show_missions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.missions_embed(), view=self)

    @discord.ui.button(label="Réclamer les XP", style=discord.ButtonStyle.success, emoji="🎁", row=2)
    async def claim_missions(self, interaction: discord.Interaction, button: discord.ui.Button):
        total, count = claim_all_weekly_missions(self.guild_id, self.user_id)
        if not count:
            await interaction.response.send_message("Aucune récompense hebdomadaire n'est actuellement disponible. Si une mission est terminée mais que le plafond quotidien est atteint, tu pourras réessayer demain.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.missions_embed(), view=self)
        await interaction.followup.send(f"🎉 {count} récompense(s) récupérée(s) : **+{total} XP Célestes**.", ephemeral=True)
