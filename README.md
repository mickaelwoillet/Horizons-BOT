# HORIZONS — Bot Discord

## Installation sous Windows
1. Installer Python 3.11 ou 3.12.
2. Lancer `install_windows.bat`.
3. Copier `.env.example` vers `.env`.
4. Remplacer `DISCORD_TOKEN` par le token du bot (ne jamais le partager).
5. Vérifier les identifiants et les rôles dans `.env`.
6. Activer les intents **Server Members Intent** et **Message Content Intent** dans le portail développeur Discord.
7. Vérifier les permissions du bot : voir les salons, envoyer des messages, intégrer des liens, lire l'historique, gérer les salons, déplacer les membres et gérer les rôles. Les commandes de modération nécessitent aussi les permissions Discord correspondantes.
8. Lancer `start_windows.bat`.

## Configuration
Les identifiants des salons propres à HORIZONS sont préremplis dans `.env.example` à partir des informations communiquées. Vérifier qu'ils correspondent toujours au serveur.
Les sept identifiants de rôles honorifiques restent à renseigner dans `RANK_ROLE_IDS`.
La traduction est facultative et désactivée sans URL LibreTranslate.

## Vérifications locales
Depuis le dossier du projet :
```bat
.venv\\Scripts\\python.exe tests\\check_project.py
```
Ce contrôle vérifie la syntaxe, les données JSON, les extensions, les commandes et le schéma SQLite. Il ne remplace pas un test connecté à Discord.

## Sécurité
Le token ne doit exister que dans le fichier `.env` local, ignoré par Git. Si un token a été partagé ou inclus dans une archive diffusée, le révoquer et en générer un nouveau dans le portail développeur Discord.

## Dashboard staff interactif — mise à jour

- `/dashboard` ouvre le poste de travail privé du membre du staff.
- Hors service, seul le bouton **Prendre mon service** est affiché.
- En service, les rubriques autorisées par le rôle deviennent accessibles.
- Les modérateurs, administrateurs et le fondateur disposent d'un sélecteur de membre et d'actions rapides : avertissement, timeout de 10 minutes, expulsion et bannissement. Un motif est obligatoire et les actions sont journalisées.
- Le bouton **Terminer mon service** clôture la session. Les commandes de modération classiques exigent également une session active.
- Le guide des commandes du staff est publié dans le salon configuré par `STAFF_COMMANDS_CHANNEL_ID`, à partir des commandes réellement chargées. Les commandes du dashboard et de gestion du service sont désormais classées dans ce guide.

Les données de service et les tâches sont conservées dans la base SQLite existante. Ne supprime pas le dossier `data/` lors de la mise à jour.

## Parcours des horizons

- `/parcours` ouvre le parcours personnel et ses cinq thèmes : Découverte, Confiance, Solidarité, Curiosité et Créativité.
- Les étapes sont facultatives et se valident par les boutons du panneau privé.
- `/parcours_badges` affiche les thèmes entièrement accomplis.
- La progression est stockée dans SQLite dans une nouvelle table non destructive. Elle ne dépend pas du nombre de messages.


## Accueil et charte HORIZONS (V1)

Les identifiants suivants sont configurés par défaut dans `config.py` et peuvent être remplacés dans `.env` :

```env
WELCOME_CHANNEL_ID=1566562049222250647
LEAVE_CHANNEL_ID=1566562049222250647
CHARTER_CHANNEL_ID=1566562055811633353
NEW_MEMBER_ROLE_ID=1566561929349304360
MEMBER_ROLE_ID=1566561934533468294
```

À l'arrivée, le bot attribue `🌱 Nouveau membre` et publie le message de bienvenue. Le message de charte est publié une seule fois et son bouton reste actif après redémarrage. Le clic ajoute `Membre` puis retire `🌱 Nouveau membre`. Les départs sont annoncés dans `Bienvenue`.

**Permissions Discord à vérifier :** activer l'intention privilégiée `Server Members Intent` dans le portail développeur ; donner au bot la permission `Gérer les rôles` et placer son rôle au-dessus des deux rôles concernés ; lui donner `Voir le salon`, `Envoyer des messages`, `Intégrer des liens` et `Lire l'historique des messages` dans les salons de charte et de bienvenue.

La charte V1 est une base communautaire générale. Si tu as un règlement officiel différent, remplace le texte dans `cogs/onboarding.py` avant publication. Le bot ne peut pas supprimer les anciens messages publiés par DraftBot : supprime ou désactive l'ancien message de charte manuellement après avoir vérifié le nouveau.


## Identité visuelle des embeds HORIZONS

Les embeds construits par les modules du bot utilisent maintenant `cogs.embed_theme.horizons_embed` :
- miniature du logo officiel HORIZONS en haut à droite ;
- couleur or par défaut, tout en conservant les couleurs fonctionnelles explicitement choisies ;
- signature HORIZONS dans le pied de message.

Au premier démarrage, le bot publie le fichier `data/assets/logo_horizons.png` une seule fois dans le salon configuré par `STAFF_COMMANDS_CHANNEL_ID` (ou `LOG_CHANNEL_ID` en secours), puis réutilise la pièce jointe Discord pour tous les embeds. Le message de dépôt contient une consigne de ne pas le supprimer.

Permissions nécessaires dans ce salon : voir le salon, envoyer des messages et joindre des fichiers. Si le bot ne peut pas publier le logo, les embeds continuent de fonctionner mais sans miniature ; vérifiez les permissions puis relancez le bot.


## Livraison finale cumulative

Lire `BILAN_FINAL_ET_INSTALLATION.md` avant installation chez dimdam's.
Les notes anciennes sont regroupées dans `docs/HISTORIQUE_DES_VERSIONS.md`.
Le fichier `.env` n'est pas fourni. Préserver la base `data/` la plus récente.

### Nouveauté V9.0 — Chaos Cosmique

Un univers narratif optionnel, activable via `/cosmos canal` puis `/cosmos activer`. Les anomalies interactives sont limitées à une par jour, les jauges persistent dans une base SQLite séparée et l'extension reste en pause par défaut. Voir `COMMANDES.md` pour le détail.

### Chaos Cosmique — univers complet optionnel

L'extension `cogs.chaos_cosmique` fournit désormais l'installation d'une catégorie dédiée, Nox, des anomalies narratives, des chroniques, une carte progressive et un inventaire. **Aucun salon n'est créé automatiquement au démarrage** : l'administrateur lance `/cosmos installer`, puis `/cosmos activer actif:True`. Toutes les commandes sont documentées dans `COMMANDES.md`. L'extension reste désactivée par défaut et conserve sa propre base SQLite.
