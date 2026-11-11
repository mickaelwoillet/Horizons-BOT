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

### V9.6 — Histoire du Chaos Cosmique
Après déploiement, lancer `/cosmos installer` (staff) pour harmoniser la catégorie existante, ajouter le salon de lecture seule `histoire-du-chaos` et y publier une présentation illustrée. La commande est conçue pour réutiliser les salons déjà créés. `/cosmos histoire` restaure le message officiel s'il a été supprimé. Conserver le fichier image dans `data/chaos_cosmique/` : il fait partie du dépôt, contrairement aux bases SQLite de production.

### V10 INFINITY — tableau de bord Nox et histoire interactive

Nouveau point d'entrée membre : **`/nox`**. Les boutons interactifs de soin, discussion, jeu, repos, exploration, carte, sac, chroniques et rencontre remplacent le besoin de mémoriser plusieurs commandes. La publication existante du salon « histoire du chaos » est mise à jour par `/cosmos installer`, avec une nouvelle illustration dans `data/chaos_cosmique/histoire_chaos_cosmique.png` et trois boutons persistants. La base SQLite existante est préservée et aucune migration destructive n'est nécessaire.

Les nouveaux dialogues et rencontres sont des scénarios locaux déterministes, pas un modèle conversationnel IA. Les événements existants, les salons, la progression, l'inventaire et les commandes de compatibilité sont conservés.

### V10.1 — INFINITY, progression des missions (version intermédiaire)
Cette livraison est une étape de développement vers la version finale, **pas encore la version finale INFINITY**.
- Le tableau `/nox` propose désormais **Mission du jour**, **Mes secrets** et **Mes rencontres**.
- Une mission personnelle est choisie de manière stable chaque jour. L'action correspondante sur Nox valide l'objectif, puis un bouton permet de récupérer une récompense cosmétique **une seule fois**.
- Les rencontres renforcent une affinité individuelle une fois par jour; des secrets peuvent se débloquer.
- Le salon Histoire du Chaos ajoute un bouton **Mission du jour**, en conservant les boutons déjà installés.
- Trois tables SQLite sont créées automatiquement au démarrage (`cosmic_missions`, `cosmic_bonds`, `cosmic_secrets`) sans supprimer les anciennes.
- L'illustration actuelle du salon Histoire n'est pas encore mise à jour pour ces nouvelles interactions : la refonte visuelle finale est prévue avant installation publique.

**État des tests :** tests statiques et compilation Python seulement. Pas de validation Discord en direct dans l'environnement de développement.

## V10.2 — Les saisons et expéditions (version de développement)

Le tableau `/nox` comporte désormais **Saison actuelle**, **Rumeur du jour** et **Expédition**. Une saison narrative dure 28 jours, propose un récit cyclique et une expédition collective de 12 contributions. Chaque membre peut apporter un éclat par jour ; la quête reste réalisable en solo. Les rumeurs sont déterministes par membre et par jour et ne promettent pas toutes un secret réel. Les tables SQLite sont créées sans effacer les précédentes.

La V10.2 est un jalon de développement, pas la livraison finale : saisons approfondies, intrigue à embranchements, graphismes du salon Histoire et tests réels Discord restent à poursuivre. Ne pas déployer si l'objectif est d'attendre la version finale.

### V10.3 — Portail des Paradoxes (développement)
Le bouton « Portail des paradoxes » du tableau `/nox` propose une mini-aventure personnelle quotidienne avec trois choix. La décision et sa conséquence sont enregistrées dans `cosmic_paradox_choices`, sans écraser les autres données. Le salon Histoire propose un bouton « Portail secret » après actualisation par `/cosmos installer`. Les récompenses sont des objets fictifs. L'ancien identifiant de bouton « Rumeur du jour » est conservé pour la compatibilité, mais son comportement ouvre désormais le portail. Les anciennes rumeurs restent dans le code pour une évolution ultérieure.

### V10.4 — Les Conspirations de l'Impossible (version de développement)
Quatre intrigues croisées à choix multiples, accessibles via le bouton « Intrigue des habitants » de `/nox`. Chaque choix est sauvegardé dans `cosmic_crossroads` (création automatique et non destructive), modifie les jauges du monde, les relations et le journal. Les interactions sont privées et limitées à un choix par jour et par membre. Validation sur un vrai serveur Discord requise avant déploiement de production.

### V10.5 — Les Échos du Destin (version de développement)

Les choix des intrigues croisées enregistrent désormais une conséquence différée dans `cosmic_echoes`.
Elle devient visible deux jours plus tard via le bouton **✉️ Échos du destin** du tableau `/nox`.
La résolution est idempotente, persistante après redémarrage et ne publie pas de message supplémentaire dans les salons.
Les anciennes intrigues déjà terminées avant V10.5 ne sont pas rétroactivement programmées.

**Vérification locale :** trois nouveaux tests SQLite réussis ; 20 tests de la suite Cosmos ont réussi, trois tests d'importation restent bloqués par l'absence de `discord.py` dans l'environnement de test. Aucun test réel Discord n'a été réalisé. Ne pas déployer avant validation finale.


## NOX TV — V10.6 (préversion)
Module optionnel `cogs/nox_tv.py`, banque de 2 PNG + 1 GIF et catalogue JSON. `/noxtv configurer salon:#salon`, `/noxtv activer actif:True`, `/noxtv tester`. Test manuel sans effet sur la programmation ; publication automatique rare, max une par jour et uniquement 12h-21h heure de Paris. Aucun deuxième bot nécessaire.

### V10.7 — NOX TV contextuel
- Priorité (80 %) aux scènes correspondant aux seuils de vitalité, affection et stabilité de Nox, si disponibles.
- Lecture seule de la base Chaos Cosmique, sans migration.
- `/noxtv statut` : salon, activation, humeur et dernière publication.
- Visuels actuels : 3 fichiers (2 images, 1 GIF) ; la galerie de 30 reste à produire.

### V10.8 — NOX TV interactif (préversion)
Les publications NOX TV possèdent trois boutons persistants : défendre Nox, soutenir Coin-Coin ou fuir. Un vote par membre et par publication, modifiable, stocké dans `data/nox_tv.sqlite3`. Les résultats sont visibles en réponse privée au clic ; le staff peut les consulter avec `/noxtv votes message_id:<ID>`. Les votes n'altèrent pas les statistiques de Chaos Cosmique. La configuration reste opt-in et les tests manuels ne consomment pas le quota quotidien. Cette version n'a pas été validée en conditions réelles sur Discord.

### V10.9 — NOX TV : verdicts et images
Deux nouvelles illustrations originales ; clôture automatique des votes le lendemain, résultat annoncé dans le salon, persistance SQLite et protection contre les doubles verdicts. Aucun changement des stats de Chaos Cosmique.


### V10.10 — NOX TV : verdicts narratifs
- 15 conclusions propres aux 5 scènes actuellement intégrées, selon le vote majoritaire.
- Votes manuels enregistrés séparément et clôturés le lendemain.
- Un vote sans participation donne désormais lieu à une conclusion neutre.
- Contrôle de validité des messages avant acceptation des votes.
- NOX TV reste désactivé par défaut ; version de développement non validée sur Discord.


### V10.11 — Scènes visuelles supplémentaires
Deux images originales ajoutées : `grille_pain_apocalypse.png` et `nox_dort_reunion.png`, avec six verdicts narratifs. Le catalogue atteint 7 médias (6 PNG, 1 GIF). Les publications restent opt-in.

## V10.12 — Galerie et verdicts
Deux nouvelles scènes illustrées (alerte tartine, conseil de crise), neuf médias disponibles, 27 conclusions spécifiques. Correction du canal de réponse des publications de test via migration SQLite non destructive.

### V10.13 — Routage des salons NOX TV
Les publications visuelles utilisent `kind` dans `data/nox_tv/catalogue.json` pour choisir le salon : Nox → NOX, canard/grille-pain/paradoxe → Anomalies, Gloups → Observatoire, exploration → Exploration, chronique → Chroniques. Les verdicts sont publiés dans Chroniques avec un lien vers la scène originale. Les identifiants sont personnalisables dans `.env` (voir `.env.example`). Le système reste opt-in et conserve les publications précédentes grâce à une migration SQLite additive (`noxtv_posts.channel_id`).

### V10.14 — NOX TV : contrôle qualité et catalogue
`/noxtv catalogue` affiche les identifiants des médias et leurs salons. `/noxtv tester scene:<identifiant>` permet de tester une scène précise sans consommer le quota automatique. Les réservations de publication sont libérées si le salon est absent ou incompatible, pour éviter de bloquer la journée. Publication automatique toujours désactivée par défaut.


### V10.15 — Paradoxe & Gloups
Deux scènes illustrées supplémentaires (11 médias au total), avec verdicts spécifiques. Les égalités de votes ne favorisent plus automatiquement le premier bouton : un verdict neutre est rendu. Publication automatique toujours désactivée par défaut.

### V10.16 — Diagnostic et sécurité des salons
Ajout de `/noxtv diagnostic` (permissions voir/écrire/embed/fichiers et vérification des salons). Un canal appartenant à un autre serveur ne peut pas recevoir une publication.

## V10.17 — Scènes et protections NOX TV

- Deux scènes supplémentaires : Mardi 2,5 (Madame Paradoxe) et Expérience 547 (professeur Gloups).
- Deux nouvelles images et six conclusions narratives.
- Les deux dernières scènes publiées sont évitées, y compris les publications manuelles (sauf sélection explicite).
- Contrôle des permissions du bot avant tout envoi ; réservation libérée si le salon ne permet pas les pièces jointes.
- Publications automatiques toujours désactivées par défaut ; tester sur Discord avant activation.

### V10.18 — Deux scènes supplémentaires NOX TV
Deux nouveaux médias (Paradoxe : grève des horloges ; Gloups : fiole rebelle) et six verdicts narratifs. Catalogue : 15 médias. Version de développement, publication automatique toujours désactivée par défaut.


### V10.19 — NOX TV : étoile animée
Nouveau GIF `nox_etoile.gif` dans le salon Nox, trois verdicts dédiés. Le catalogue comporte 16 médias (14 PNG, 2 GIF). Publication automatique désactivée par défaut.


### V10.20 — Outils de préparation de NOX TV
- `/noxtv apercu scene:<identifiant>` : prévisualisation **éphémère** d'une image ou d'un GIF sans message public, vote ni modification du calendrier.
- `/noxtv diagnostic` indique aussi l'état d'activation et le nombre de médias présents.
- `/noxtv tester` vérifie désormais la présence du serveur avant d'essayer de publier.
- Les 16 médias précédents sont conservés, aucune base SQLite existante n'est supprimée.


### V10.21 — Renforcement de sécurité NOX TV
- Vérification du fichier média et blocage des chemins hors du dossier `data/nox_tv` avant publication.
- Contrôle de l'appartenance au serveur et des permissions du salon Chroniques avant un verdict.
- Échec de lecture d'image traité sans bloquer les publications futures.
- Publication automatique toujours désactivée par défaut ; tests Discord nécessaires.


### V10.22 — Correctifs NOX TV
- Aperçu privé : correction du traitement des médias manquants (plus de variables non définies), réponse Discord explicite.
- Chroniques : pas de repli vers un autre salon lorsque la destination des verdicts est invalide.
- Aucune migration destructive, aucun nouveau média annoncé.


## V10.23 — Fiabilisation du catalogue multimédia
Les médias sont désormais validés avant publication ou aperçu (chemin autorisé, format, taille maximale de 8 Mio, champs requis, identifiant unique). Un catalogue JSON illisible ne fait plus planter la sélection : aucune publication n’est envoyée. La galerie reste à 16 médias.

### V10.24 — Rotation indépendante des tests
Les publications manuelles `/noxtv tester` n'influencent plus la sélection des deux dernières scènes automatiques. Les tests restent traçables pour leurs votes et leurs verdicts, mais n'affectent pas la rotation de production. Identifiants de scène limités à 80 caractères. Publication automatique toujours désactivée par défaut.

### NOX TV V10.25 — Audit de la galerie
`/noxtv audit` (staff) : vérifie le catalogue complet, les fichiers réellement accessibles, les GIF, les salons de destination et les trois verdicts de chaque scène, sans publier ni modifier SQLite.

### NOX TV V10.26 — Simulation sans publication
`/noxtv simulation` (staff) propose une scène en fonction de l’humeur de Nox, des deux dernières publications automatiques et du salon prévu. Aucun message public, vote, changement SQLite ou réservation de calendrier. Le tirage réel peut différer.

### V10.27 — Première animation originale du Canard Suprême
GIF `canard_matraque_anime.gif` : Coin-Coin agite sa cuisse de poulet dans l’Observatoire. Scène `canard_matraque_anime` destinée au salon Anomalies, trois verdicts dédiés. Aucun changement de commande ou de base de données.

### V10.28 — Panique du grille-pain
Nouveau GIF original `grille_pain_panique_anime.gif`, 10 images, routage Anomalies, trois verdicts propres. NOX TV reste désactivé par défaut.


## V10.29 - Animation Grille-Pain 3000
Animation GIF refaite : Nox, Coin-Coin et Grille-Pain 3000 dans une vraie scene de catastrophe. Le catalogue et les identifiants restent inchanges. Version de developpement, a tester sur Discord.


### V10.31 — Animations distinctes
Le GIF Coin-Coin a été remplacé par une scène de poursuite originale. Nouveau GIF Nox affamé, catalogue de 19 scènes. Animations à vérifier en conditions Discord.

### V10.32 — Bilan NOX TV
`/noxtv bilan` affiche en privé les publications automatiques, tests, votes actuels, membres votants et verdicts, sans modifier la base.

### V10.33 — Compatibilité des tests GIF
Correction du test historique de Coin-Coin : contrôle de la résolution minimale et du format 16:9 plutôt que de dimensions fixes devenues obsolètes après remplacement de son animation. Aucun changement aux données ou aux horaires de publication.

### V10.35 — Quatre scènes illustrées supplémentaires
Ajout de quatre PNG originaux : conférence de Coin-Coin, ascenseur temporel, sieste de Nox et pluie de bulles de Gloups. 25 médias au catalogue.

### V10.36 — Galerie 30/30
Cinq nouvelles scènes originales : planète biscuit, couronne rebelle, réveil temporel, tartine candidate et portail des chaussettes. Les tests Discord réels restent nécessaires.


### V10.37 — Correctif audit NOX TV
Ajout des trois verdicts de `nox_faim_anime` (GIF de Nox affamé). Aucune modification des médias, salons, horaires ni paramètres. Relancer `/noxtv audit` après déploiement : résultat attendu 30/30, zéro anomalie.

### V10.54 — NOX TV
Cinq anciennes sous-commandes (`statut`, `diagnostic`, `audit`, `simulation`, `catalogue`) ont été migrées vers les boutons de `/noxtv panneau`.

### V10.85.10 — Surprises collectives NOX
`/noxsurprise` (administrateur) : choisir parmi 4 thèmes (absurdité, question, mini-défi, douceur) et un salon. NOX publie via webhook ; pas de publication automatique. 32 répliques dans `data/nox/surprises_collectives.json`.

### NOX Junior V0.1 — développement séparé
Deux commandes : `/monnox` et `/givemonnox`. Données persistantes : `data/nox_junior.sqlite3` (ne jamais écraser en mise à jour). Les soins du NOX collectif sont lus depuis `data/nox_refuge.sqlite3`. La V0.1 ne contient que les fondations ; les jeux et images sont à venir. Tests locaux : `python -m unittest discover -s tests -p test_nox_junior_engine.py`.

### NOX Junior V0.2 — vie quotidienne
Six soins accessibles depuis le panneau privé `/monnox`, cinq jauges à évolution temporelle limitée, humeur contextuelle, journal des dernières actions et actualisation. Migration SQLite automatique non destructive depuis V0.1 (colonne `last_decay`). Préserver `data/nox_junior.sqlite3` et `data/nox_refuge.sqlite3` lors de l'installation. Tests locaux : `python -m unittest discover -s tests -p test_nox_junior_v02.py`. Pas encore validé sur Discord réel.


## NOX Junior V0.3
Trois mini-jeux, affinités persistantes et commande publique `/montrermonnox` avec portrait local. Voir `NOX_JUNIOR_V0_3_RAPPORT.md`.

### NOX Junior V0.4
Cinq régions d'exploration et six mini-jeux disponibles dans `/monnox`. Voir `NOX_JUNIOR_V0_4_RAPPORT.md`. Version de développement : tester sur un serveur Discord dédié avant production.


## NOX Junior V0.5
Voir `NOX_JUNIOR_V0_5_RAPPORT.md` pour les nouveautés, limites et tests.

### NOX Junior V0.7 (développement)
Rencontres cosmiques : invitation depuis `/monnox`, acceptation/refus par le destinataire, trois mini-jeux coopératifs nécessitant une action de chacun des deux membres, journal et affinités mis à jour. Aucune notification directe : le destinataire consulte `/monnox` → Rencontres. Voir `NOX_JUNIOR_V0_7_RAPPORT.md`. Ne pas remplacer la version de production avant essais Discord.

### NOX Junior V0.8
Moteur visuel hors ligne (`cogs/nox_junior_visual.py`), bouton Portrait, prévisualisation des chambres et portraits publics adaptés au stade de croissance. Voir `NOX_JUNIOR_V0_8_RAPPORT.md`.

### NOX Junior V0.9
Trois manches par jeu coopératif, progression enregistrée dans `junior_encounter_rounds`, décisions distinctes et récompense finale unique. Voir `NOX_JUNIOR_V0_9_RAPPORT.md`. Les parties actives de V0.7/V0.8 doivent de préférence être terminées avant migration ; une rencontre active antérieure peut reprendre au début des nouvelles manches.


## NOX Junior V1.0
Neuf couleurs à l'adoption, dont **🌈 Arc-en-ciel**. Les visuels PNG sont calculés localement.
Installer les dépendances avec `pip install -r requirements.txt` (Pillow est requis).
**Déploiement prudent :** sauvegarder les fichiers SQLite et `.env`, terminer les rencontres en cours, tester d'abord sur un serveur Discord distinct.
Le moteur a des tests automatisés, mais aucune recette de bout en bout sur Discord n'est attestée.
