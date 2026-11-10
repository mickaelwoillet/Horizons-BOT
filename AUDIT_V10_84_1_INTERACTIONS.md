# HORIZONS V10.84.1 — Audit cumulatif des interactions

Source : `HORIZONS_V10_83_BOUTONS_NOXTV_PERSONNALISES.zip`. Audit statique, sans connexion Discord ni modification des modules exécutables.

## Résultats mesurés
- 225 entrées dans le ZIP, 108 fichiers Python.
- 74 classes `View` détectées par analyse AST.
- 128 méthodes avec décorateurs de boutons/sélections détectées.
- 56 définitions de commandes détectées.
- 27 tâches `tasks.loop` détectées.
- 0 erreurs de syntaxe Python.

## Points de vigilance
- Un `timeout=None` ne garantit pas à lui seul la persistance : les composants doivent posséder des `custom_id` stables et les vues doivent être réenregistrées au démarrage.
- Les vues temporaires ne sont pas nécessairement des bugs : vérifier si le message est éphémère ou permanent.
- Les contrôles de permissions doivent être vérifiés côté callback, pas seulement dans l’affichage des boutons.
- Vérifier les limites Discord : cinq rangées de composants, cinq boutons par rangée, un menu de sélection occupant une rangée.
- Les tests de bout en bout nécessitent un serveur Discord de test et les identifiants configurés.

## Inventaire des vues

| Module | Classe | Ligne | Timeout détecté |
|---|---|---:|---|
| `cogs/arcade_games.py` | `ArcadeMenuView` | 102 | `180` |
| `cogs/arcade_games.py` | `ArcadeNightView` | 1547 | `600` |
| `cogs/arcade_games.py` | `BaseGameView` | 474 | `timeout` |
| `cogs/arcade_games.py` | `ChallengeInviteView` | 410 | `120` |
| `cogs/arcade_games.py` | `ChallengeSetupView` | 348 | `120` |
| `cogs/arcade_games.py` | `CollectiveGameMenu` | 218 | `180` |
| `cogs/arcade_games.py` | `DifficultyView` | 314 | `120` |
| `cogs/arcade_games.py` | `NavalPrivateView` | 1169 | `3600` |
| `cogs/arcade_games.py` | `PetitBacView` | 960 | `180` |
| `cogs/arcade_progress.py` | `ProgressView` | 361 | `180` |
| `cogs/birthdays.py` | `BirthdayPanel` | 40 | `None` |
| `cogs/celestial_treasures.py` | `ScratchView` | 225 | `180` |
| `cogs/celestial_treasures.py` | `TreasurePanelView` | 264 | `None` |
| `cogs/celestial_treasures.py` | `TreasureStarsView` | 258 | `180` |
| `cogs/centre_horizons.py` | `CentreView` | 523 | `600` |
| `cogs/centre_horizons.py` | `MoodEraseConfirm` | 413 | `90` |
| `cogs/chaos_cosmique.py` | `CosmicChoices` | 185 | `None` |
| `cogs/chaos_cosmique.py` | `CosmicCrossroadView` | 656 | `300` |
| `cogs/chaos_cosmique.py` | `CosmicExpeditionView` | 699 | `180` |
| `cogs/chaos_cosmique.py` | `CosmicExplore` | 828 | `180` |
| `cogs/chaos_cosmique.py` | `CosmicMissionClaim` | 816 | `180` |
| `cogs/chaos_cosmique.py` | `CosmicParadoxView` | 673 | `180` |
| `cogs/chaos_cosmique.py` | `CosmicStoryButtons` | 843 | `None` |
| `cogs/chaos_cosmique.py` | `NoxPanel` | 709 | `None` |
| `cogs/circle_proposals.py` | `CircleInterestView` | 71 | `None` |
| `cogs/circle_proposals.py` | `CircleProposalEntry` | 109 | `None` |
| `cogs/circle_proposals.py` | `CircleStaffView` | 189 | `None` |
| `cogs/community_hub.py` | `DashboardView` | 52 | `180` |
| `cogs/community_hub.py` | `IdeaPanel` | 80 | `None` |
| `cogs/community_hub.py` | `IdeaVoteView` | 29 | `None` |
| `cogs/community_hub.py` | `ThanksPanel` | 120 | `None` |
| `cogs/community_hub.py` | `ThanksSelectView` | 116 | `180` |
| `cogs/events.py` | `EventRSVPView` | 15 | `None` |
| `cogs/experiences.py` | `InterestView` | 80 | `None` |
| `cogs/giveaways.py` | `GiveawayView` | 30 | `None` |
| `cogs/horizons_arcade.py` | `AnswerView` | 109 | `300` |
| `cogs/horizons_arcade.py` | `ArcadeLaunchView` | 315 | `None` |
| `cogs/horizons_arcade.py` | `CoinView` | 123 | `60` |
| `cogs/horizons_arcade.py` | `CollectiveGameView` | 194 | `600` |
| `cogs/horizons_arcade.py` | `ReflexView` | 149 | `20` |
| `cogs/horizons_dashboard.py` | `DashboardView` | 88 | `900` |
| `cogs/horizons_features.py` | `AffinityPanel` | 60 | `None` |
| `cogs/horizons_features.py` | `MoodPanel` | 125 | `None` |
| `cogs/horizons_features.py` | `MoodSelectView` | 119 | `180` |
| `cogs/horizons_path.py` | `PathView` | 74 | `300` |
| `cogs/jokes.py` | `JokeView` | 20 | `180` |
| `cogs/mission_hub.py` | `MissionHubView` | 57 | `None` |
| `cogs/mission_hub.py` | `MissionSteps` | 37 | `180` |
| `cogs/nox_tv.py` | `NoxTVChoices` | 84 | `None` |
| `cogs/nox_tv.py` | `NoxTVDashboard` | 434 | `900` |
| `cogs/onboarding.py` | `AcceptCharterView` | 14 | `None` |
| `cogs/quizzes.py` | `QuizView` | 42 | `600` |
| `cogs/riddles.py` | `RiddleView` | 15 | `300` |
| `cogs/role_panels.py` | `RolePanelView` | 101 | `None` |
| `cogs/salon_harmony.py` | `ActivitySalonView` | 43 | `None` |
| `cogs/salon_harmony.py` | `CollectiveSalonView` | 79 | `None` |
| `cogs/smart_welcome.py` | `DiscoveryLinksView` | 152 | `None` |
| `cogs/smart_welcome.py` | `WelcomeView` | 111 | `None` |
| `cogs/staff_dashboard.py` | `CapsuleStaffView` | 408 | `600` |
| `cogs/staff_dashboard.py` | `DashboardView` | 440 | `900` |
| `cogs/staff_dashboard.py` | `EventBoardView` | 334 | `600` |
| `cogs/staff_dashboard.py` | `EventsStaffView` | 151 | `600` |
| `cogs/staff_dashboard.py` | `RegardboardView` | 239 | `600` |
| `cogs/staff_dashboard.py` | `SectionsGridView` | 178 | `600` |
| `cogs/staff_dashboard.py` | `TaskFilterView` | 1041 | `600` |
| `cogs/staff_dashboard.py` | `ThematicStaffView` | 702 | `600` |
| `cogs/staff_tools.py` | `AnonymousPanel` | 120 | `None` |
| `cogs/tickets.py` | `TicketPanelView` | 88 | `None` |
| `cogs/tickets.py` | `TicketView` | 57 | `None` |
| `cogs/today_hub.py` | `ActivityProposalView` | 195 | `180` |
| `cogs/today_hub.py` | `ChallengeView` | 213 | `180` |
| `cogs/today_hub.py` | `MysteryView` | 264 | `180` |
| `cogs/today_hub.py` | `TodayView` | 273 | `None` |
| `cogs/weekly_animations.py` | `WeeklyParticipationView` | 66 | `None` |

## Boucles programmées

| Module | Fonction | Ligne | Décorateur |
|---|---|---:|---|
| `cogs/automod.py` | `expire_tempbans` | 375 | `tasks.loop(minutes=1)` |
| `cogs/birthdays.py` | `daily_birthdays` | 62 | `tasks.loop(time=time(hour=9, minute=0, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/celestial_treasures.py` | `refresh_treasures_info` | 380 | `tasks.loop(hours=2)` |
| `cogs/chaos_cosmique.py` | `cosmic_clock` | 933 | `tasks.loop(minutes=60)` |
| `cogs/community.py` | `daily_question` | 53 | `tasks.loop(time=time(hour=11, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/continuity.py` | `monitor` | 102 | `tasks.loop(hours=CHECK_INTERVAL_HOURS)` |
| `cogs/events.py` | `event_reminders` | 175 | `tasks.loop(minutes=5)` |
| `cogs/experiences.py` | `expire_activity_requests` | 144 | `tasks.loop(minutes=10)` |
| `cogs/experiences.py` | `publish_weekly_missions` | 174 | `tasks.loop(minutes=30)` |
| `cogs/giveaways.py` | `finish_due` | 209 | `tasks.loop(minutes=1)` |
| `cogs/horizons_arcade.py` | `refresh_arcade_info` | 385 | `tasks.loop(hours=2)` |
| `cogs/horizons_daily.py` | `horizon_of_day` | 154 | `tasks.loop(time=time(hour=9, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/horizons_daily.py` | `weekly_debate` | 193 | `tasks.loop(time=time(hour=19, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/horizons_dashboard.py` | `daily_snapshot` | 168 | `tasks.loop(time=time(hour=2, minute=10, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/jokes.py` | `daily_joke` | 69 | `tasks.loop(time=time(hour=15, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/nox_tv.py` | `clock` | 639 | `tasks.loop(minutes=60)` |
| `cogs/publication_calendar.py` | `daily_inspiration` | 174 | `tasks.loop(time=time(hour=19, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/publication_calendar.py` | `daily_positive_message` | 208 | `tasks.loop(time=time(hour=21, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/publication_calendar.py` | `daily_quiz` | 149 | `tasks.loop(time=time(hour=13, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/publication_calendar.py` | `daily_thematic_event` | 219 | `tasks.loop(time=time(hour=8, minute=0, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/regard_du_jour.py` | `scheduler` | 625 | `tasks.loop(minutes=1)` |
| `cogs/riddles.py` | `daily_riddle` | 62 | `tasks.loop(time=time(hour=17, minute=30, tzinfo=LOCAL_TIMEZONE))` |
| `cogs/seasons.py` | `season_watch` | 124 | `tasks.loop(minutes=10)` |
| `cogs/server_guides.py` | `publish_guides` | 310 | `tasks.loop(minutes=30)` |
| `cogs/smart_welcome.py` | `followup_loop` | 370 | `tasks.loop(hours=1)` |
| `cogs/today_hub.py` | `maintenance` | 634 | `tasks.loop(hours=6)` |
| `cogs/weekly_animations.py` | `friday_animation` | 110 | `tasks.loop(time=time(hour=19, minute=30, tzinfo=LOCAL_TIMEZONE))` |

## Ordre des corrections proposées

1. Tester et fiabiliser les vues persistantes et les `custom_id` de tous les panneaux permanents.
2. Contrôler les droits par rôle et les réponses aux interactions (defer, suivi, gestion des erreurs).
3. Ajouter une page de contrôle des tâches sans changer les planifications existantes.
4. Ajouter le sélecteur paginé NOX TV, en conservant les identifiants de scènes et de votes.
5. Ajouter diagnostic et sauvegarde SQLite par API de backup, sans copier une base ouverte à chaud.

## Garantie de cette livraison

Cette étape ne modifie aucun module Python, fichier JSON de configuration ou base de données. Elle ajoute uniquement ce rapport d’audit à la V10.83. La version en production peut rester inchangée.
