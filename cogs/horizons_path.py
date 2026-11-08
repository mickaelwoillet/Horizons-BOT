"""Parcours des horizons : progression facultative en cinq thèmes, directement dans Discord."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from .storage import db

THEMES = {
    "decouverte": ("🌅 Découverte", "Faire ses premiers pas et découvrir la communauté.", [
        "Repérer deux salons qui m'intéressent.",
        "Découvrir une activité ou un événement HORIZONS.",
        "Partager une passion, une recommandation ou un centre d'intérêt.",
    ]),
    "confiance": ("💜 Confiance", "Avancer à son rythme et prendre sa place.", [
        "Identifier un sujet sur lequel j'aime échanger.",
        "Oser participer à une discussion, même brièvement.",
        "Partager une idée ou une expérience si j'en ai envie.",
    ]),
    "solidarite": ("🤝 Solidarité", "Faire vivre l'entraide et l'attention aux autres.", [
        "Découvrir les espaces d'entraide et de soutien.",
        "Encourager ou remercier un membre.",
        "Participer à une action ou initiative collective.",
    ]),
    "curiosite": ("🔎 Curiosité", "Apprendre, explorer et rester ouvert aux découvertes.", [
        "Découvrir un sujet ou une ressource proposée sur HORIZONS.",
        "Poser une question ou partager une découverte.",
        "Participer à un quiz, un échange ou une activité de découverte.",
    ]),
    "creativite": ("🎨 Créativité", "Imaginer et contribuer à la vie de la communauté.", [
        "Repérer une activité créative ou ludique.",
        "Proposer une idée, un jeu ou un thème.",
        "Contribuer à une animation ou à un projet collectif.",
    ]),
}


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress_for(guild_id: int, user_id: int) -> dict[str, set[int]]:
    result = {key: set() for key in THEMES}
    with db() as conn:
        rows = conn.execute(
            "SELECT theme_key,step_number FROM horizons_path_progress WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchall()
    for row in rows:
        if row["theme_key"] in result:
            result[row["theme_key"]].add(int(row["step_number"]))
    return result


def overview_embed(progress: dict[str, set[int]]) -> discord.Embed:
    total = sum(len(v) for v in progress.values())
    embed = horizons_embed(
        title="🧭 Le Parcours des horizons",
        description=("Cinq chemins pour découvrir, contribuer et trouver sa place sur HORIZONS.\n"
                     "Choisis librement les étapes qui te parlent : il n'y a ni obligation, ni classement."),
        color=discord.Color.teal(),
    )
    for key, (title, description, steps) in THEMES.items():
        done = len(progress[key])
        marks = "🟩" * done + "⬜" * (len(steps) - done)
        status = " — **Thème accompli** ✨" if done == len(steps) else ""
        embed.add_field(name=f"{title} · {done}/{len(steps)}{status}", value=f"{marks}\n{description}", inline=False)
    embed.add_field(name="Progression globale", value=f"**{total}/15 étapes** validées", inline=False)
    embed.set_footer(text="HORIZONS • Tu peux avancer à ton rythme. Les étapes sont déclaratives et facultatives.")
    return embed


class PathView(discord.ui.View):
    def __init__(self, cog: "HorizonsPath", owner_id: int, progress: dict[str, set[int]]):
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id
        self.progress = progress
        self.theme_key = "decouverte"
        options = [discord.SelectOption(label=v[0], value=k, description=v[1][:100], emoji=v[0].split()[0]) for k, v in THEMES.items()]
        self.theme_select = discord.ui.Select(placeholder="Choisir un thème", min_values=1, max_values=1, options=options)
        self.theme_select.callback = self.choose_theme
        self.add_item(self.theme_select)
        self.validate_button = discord.ui.Button(label="Valider la prochaine étape", emoji="✨", style=discord.ButtonStyle.success)
        self.validate_button.callback = self.validate_next
        self.add_item(self.validate_button)
        self.refresh_button = discord.ui.Button(label="Actualiser", emoji="🔄", style=discord.ButtonStyle.secondary)
        self.refresh_button.callback = self.refresh
        self.add_item(self.refresh_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ce parcours est personnel. Lance `/parcours` pour consulter le tien.", ephemeral=True)
            return False
        return True

    async def choose_theme(self, interaction: discord.Interaction):
        self.theme_key = self.theme_select.values[0]
        await interaction.response.edit_message(embed=overview_embed(self.progress), view=self)

    async def validate_next(self, interaction: discord.Interaction):
        steps = THEMES[self.theme_key][2]
        done = self.progress[self.theme_key]
        next_step = next((i for i in range(1, len(steps) + 1) if i not in done), None)
        if next_step is None:
            await interaction.response.send_message("Ce thème est déjà entièrement accompli. Tu peux en choisir un autre !", ephemeral=True)
            return
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO horizons_path_progress(guild_id,user_id,theme_key,step_number,completed_at) VALUES(?,?,?,?,?)",
                (interaction.guild_id, self.owner_id, self.theme_key, next_step, stamp()),
            )
        self.progress[self.theme_key].add(next_step)
        if len(self.progress[self.theme_key]) == len(steps):
            features = self.cog.bot.get_cog("HorizonsFeatures")
            if features and interaction.guild and isinstance(interaction.user, discord.Member):
                await features.check_achievements(interaction.guild, interaction.user)
            await interaction.response.edit_message(embed=overview_embed(self.progress), view=self)
            await interaction.followup.send(f"✨ Bravo ! Tu as terminé le thème **{THEMES[self.theme_key][0]}**. Ton badge est également ajouté à tes succès HORIZONS.", ephemeral=True)
        else:
            await interaction.response.edit_message(embed=overview_embed(self.progress), view=self)

    async def refresh(self, interaction: discord.Interaction):
        self.progress = progress_for(interaction.guild_id, self.owner_id)
        await interaction.response.edit_message(embed=overview_embed(self.progress), view=self)


class HorizonsPath(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="parcours", description="Découvrir et suivre ton Parcours des horizons.")
    async def parcours(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette fonctionnalité est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        progress = progress_for(interaction.guild_id, interaction.user.id)
        view = PathView(self, interaction.user.id, progress)
        await interaction.response.send_message(embed=overview_embed(progress), view=view, ephemeral=True)

    @app_commands.command(name="parcours_badges", description="Consulter les thèmes accomplis et tes badges HORIZONS.")
    async def parcours_badges(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette fonctionnalité est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        progress = progress_for(interaction.guild_id, interaction.user.id)
        badges = [title for key, (title, _, steps) in THEMES.items() if len(progress[key]) == len(steps)]
        message = "\n".join(f"🏅 {badge}" for badge in badges) if badges else "Tu n'as pas encore débloqué de badge. Chaque thème se complète à ton rythme."
        await interaction.response.send_message(embed=horizons_embed(title="🏅 Tes badges HORIZONS", description=message, color=discord.Color.gold()), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HorizonsPath(bot))
