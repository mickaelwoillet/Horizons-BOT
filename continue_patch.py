from pathlib import Path
p=Path('/mnt/data/horizons_v73/Bot Horizons')
f=p/'cogs/circle_guides.py';s=f.read_text()
s=s.replace('"""Publie ou actualise les deux guides permanents des Cercles."""','"""Maintient un seul panneau permanent dans Cercles HORIZONS."""')
s=s.replace('        self.bot = bot\n\n    async def cog_load', '        self.bot = bot\n        self._guide_refreshed = False\n\n    async def cog_load')
s=s.replace('        self._guide_refreshed = True\n        channel = await self.resolve_channel(CIRCLES_CHANNEL_ID)', '        channel = await self.resolve_channel(CIRCLES_CHANNEL_ID)')
s=s.replace('        if not isinstance(channel, discord.TextChannel):\n            return', '        if not isinstance(channel, discord.TextChannel):\n            return\n        self._guide_refreshed = True',1)
s=s.replace('                await edit_official_panel(message, embed=embed, view=CircleProposalEntry(), allowed_mentions=discord.AllowedMentions.none())\n            else:', '                await edit_official_panel(message, embed=embed, view=CircleProposalEntry(), allowed_mentions=discord.AllowedMentions.none())\n                with db() as conn:\n                    conn.execute("INSERT INTO circle_guide_publications (guild_id,channel_id,guide_key,message_id,published_at) VALUES (?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(guild_id,channel_id,guide_key) DO UPDATE SET message_id=excluded.message_id,published_at=CURRENT_TIMESTAMP", (channel.guild.id, CIRCLES_CHANNEL_ID, "cercles_horizons", message.id))\n            else:')
s=s.replace('if guide_key == "proposer_un_cercle" else message.edit(embed=embed, view=None, allowed_mentions=discord.AllowedMentions.none())','if guide_key == "cercles_horizons" else message.edit(embed=embed, view=None, allowed_mentions=discord.AllowedMentions.none())')
s=s.replace('if guide_key == "proposer_un_cercle" else None','if guide_key == "cercles_horizons" else None')
s=s.replace('if guide_key == "proposer_un_cercle" else _plain_send','if guide_key == "cercles_horizons" else send_official_panel')
s=s.replace('description="Publier ou actualiser les deux guides permanents des Cercles HORIZONS."','description="Actualiser le panneau unique des Cercles HORIZONS."')
s=s.replace('        proposal, circles = self.build_guides()','        _, circles = self.build_guides()')
f.write_text(s)
# Keep retired salon IDs out of env example and explicitly warn about server deletions.
f=p/'MIGRATION_V7_2_EN_COURS.md';f.write_text('''# Migration HORIZONS V7.2 — travail en cours\n\nTrois regroupements approuvés : suggestions → boîte-à-idées ; proposer-un-cercle → cercles-horizons ; initiatives → activités-ensemble.\n\nNe supprimer aucun salon automatiquement avant la vérification de son historique et des permissions. Les suppressions Discord ne sont pas réalisées par ce patch.\n\nCircuit des Cercles : un panneau dans cercles-horizons, avec le bouton Proposer un Cercle ; le formulaire, les validations staff et les publications doivent rester reliés à ce salon.\n\nÀ finaliser avant livraison : audit des autres producteurs de messages, persistance du contrôle anti-spam, revue des horaires, synchronisation aide/aidestaff et vérifications de l'ensemble des cogs.\n''',encoding='utf-8')
import ast
for x in p.rglob('*.py'): ast.parse(x.read_text(encoding='utf-8'),filename=str(x))
print('AST OK',len(list(p.rglob('*.py'))))
