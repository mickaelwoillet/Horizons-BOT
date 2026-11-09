from pathlib import Path
import json
p=Path('/mnt/data/horizons_v73/Bot Horizons')
# New destinations: alias former env keys to retained salons, even if old .env overrides.
c=p/'config.py'; s=c.read_text()
s=s.replace('SUGGESTION_CHANNEL_ID = env_int("SUGGESTION_CHANNEL_ID", 1566620913254932633)', 'SUGGESTION_CHANNEL_ID = env_int("IDEAS_CHANNEL_ID", 1567300011165880451)  # Salon unique : boîte à idées')
s=s.replace('CIRCLE_PROPOSALS_CHANNEL_ID = env_int("CIRCLE_PROPOSALS_CHANNEL_ID", 1568998134162522234)', 'CIRCLE_PROPOSALS_CHANNEL_ID = env_int("CIRCLES_CHANNEL_ID", 1568998630831169666)  # Circuit réunifié')
c.write_text(s)
# One public circle panel, no second guide publication.
f=p/'cogs/circle_guides.py';s=f.read_text()
start=s.index('    @commands.Cog.listener()\n    async def on_ready(self):')
end=s.index('    def build_guides(',start)
s=s[:start]+'''    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self, "_guide_refreshed", False):
            return
        self._guide_refreshed = True
        channel = await self.resolve_channel(CIRCLES_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            with db() as conn:
                row = conn.execute("SELECT message_id FROM circle_guide_publications WHERE guild_id=? AND channel_id=? AND guide_key=?", (channel.guild.id, CIRCLES_CHANNEL_ID, 'cercles_horizons')).fetchone()
            message = None
            if row and row[0]:
                try:
                    candidate = await channel.fetch_message(int(row[0]))
                    if candidate.author.id == self.bot.user.id:
                        message = candidate
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            if message is None:
                async for candidate in channel.history(limit=250):
                    if candidate.author.id == self.bot.user.id and any('Cercles HORIZONS' in (e.title or '') for e in candidate.embeds):
                        message = candidate
                        break
            if message:
                _, embed = self.build_guides()
                await edit_official_panel(message, embed=embed, view=CircleProposalEntry(), allowed_mentions=discord.AllowedMentions.none())
            else:
                log.warning("Guide Cercles introuvable : aucune publication automatique pour éviter les doublons")
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Impossible d'actualiser le panneau des Cercles")

'''+s[end:]
s=s.replace('value=f"Propose ton propre Cercle dans <#{CIRCLE_PROPOSALS_CHANNEL_ID}>. "\n                  "L\'équipe l\'étudiera avant toute ouverture.",','value="Clique sur **Proposer un Cercle** sous ce panneau. L’équipe étudiera ton formulaire privé avant toute publication.",')
s=s.replace('        results = await self.publish_or_update(\n            interaction.guild, CIRCLE_PROPOSALS_CHANNEL_ID,\n            "proposer_un_cercle", proposal, "📌 Fonctionnement — Proposer un Cercle",\n        )\n','')
s=s.replace('            "Guides des Cercles HORIZONS :\\n" + results + "\\n" + results2,','            "Guide unique des Cercles HORIZONS :\\n" + results2,')
# Ensure manual guide command also attaches the button to the retained panel.
s=s.replace('"cercles_horizons", circles, "📌 Fonctionnement des Cercles HORIZONS",','"cercles_horizons", circles, "📌 Fonctionnement des Cercles HORIZONS",')
f.write_text(s)
# panel publication helper supports view if circles
s=f.read_text(); print('publish section',s[s.index('    async def publish_or_update'):s.index('    @app_commands.command(',s.index('    async def publish_or_update'))][-1800:])
# Remove deleted names from active visual config.
v=p/'visual_identity.json'; cfg=json.loads(v.read_text()); retired={'1566620913254932633','1566852470003474512','1568998134162522234'}
for key in ('channel_names','category_names'): cfg[key]={k:val for k,val in cfg[key].items() if k not in retired}
v.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
# Env example remove retired IDs including inventory rows, leave operational aliases pointing to retained IDs.
e=p/'.env.example';lines=e.read_text().splitlines();out=[]
for line in lines:
 if any(x in line for x in retired):
  if line.startswith('SUGGESTION_CHANNEL_ID='):out.append('SUGGESTION_CHANNEL_ID=1567300011165880451 # Alias historique vers boite-a-idees')
  elif line.startswith('CIRCLE_PROPOSALS_CHANNEL_ID='):out.append('CIRCLE_PROPOSALS_CHANNEL_ID=1568998630831169666 # Alias historique vers cercles-horizons')
  else:continue
 else:out.append(line)
e.write_text('\n'.join(out)+'\n')
