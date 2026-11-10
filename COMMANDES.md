## V10.75 — NOX : carte du monde

La commande slash `/cosmos carte` est remplacée par le bouton **Carte du monde** du panneau `/nox`. La carte conserve ses zones débloquées et le parcours d’exploration. Les commandes staff sensibles restent inchangées.

## V10.74 — NOX TV : actions en boutons

Dans le panneau **NOX TV** accessible depuis `/dashboard` ou NOX, les boutons **Votes**, **Activer** et **Désactiver** remplacent les anciennes commandes slash `/noxtv votes` et `/noxtv activer`. Le bouton Votes ouvre un formulaire pour l’identifiant du message. Les permissions de gestion du serveur sont vérifiées à chaque interaction. La configuration du salon et les tests de scènes restent accessibles par leurs commandes existantes.


## Migration V10.71 — Event

Les actions **Créer un événement**, **Annuler un concours** et **Nouveau tirage** sont accessibles par boutons dans `/dashboard` → **Event**. Les commandes slash `/evenement_creer`, `/giveaway annuler` et `/giveaway reroll` ont été retirées. La création de concours `/giveaway creer` reste disponible.

## Migration V10.69 — Capsules staff

Les anciennes commandes slash `/capsule_question`, `/capsule_attente` et `/capsule_moderer` ne sont plus enregistrées. Utiliser `/dashboard` → **Capsules staff** → **Question du mois**, **Contributions en attente** ou **Modérer une contribution**. Les droits « Gérer le serveur » et la prise de service sont requis. Les anciennes mentions ci-dessous sont historiques et ne constituent pas une liste des commandes disponibles.

# V10.68 — Regroupements des panneaux (migration progressive)

**Membres :** `/centre` → « Le Regard du Jour » permet de proposer un article (formulaire) et consulter ses points ; « Mes Capsules du Temps » reste l’espace personnel pour créer, ouvrir ou retirer ses capsules. Les commandes existantes restent disponibles pendant les vérifications.

**Staff :** `/dashboard` → « Regardboard » (diagnostic, propositions, validations), « Event » (agenda, fermeture d’inscriptions, lancement et arrêt de quiz), « Capsules staff » (contributions en attente et question du mois), « NOX TV » (panneau existant). Les actions de création d’événements, de concours et les actions avancées non encore migrées restent en slash ; aucune fonctionnalité n’est annoncée comme migrée tant que son formulaire n’existe pas.

**Aides :** `/aide` et `/aidestaff` sont générées à partir des commandes réellement chargées et indiquent désormais ces accès par panneaux. **Nombre de commandes inchangé : 96.** Les contrôles statiques ne remplacent pas les tests Discord.

---

## V10.64 — Nettoyage des commandes inutilisées

Les commandes `/ping`, `/traduire`, `/renvoyer_bienvenue`, `/test_bienvenue_mp`, `/ticket_ouvrir` et `/ticket_fermer` ne sont plus enregistrées comme commandes slash. Les panneaux de tickets et leurs boutons d’ouverture/fermeture sont conservés. Le guide d’accueil automatique est conservé. La migration des groupes Affinités, Regard, Event et Capsules vers des boutons est planifiée, mais **pas encore réalisée** dans cette version.

## V10.60 — Jeux rapides dans le Centre

Les commandes `/blague` et `/devinette` ont été remplacées par **`/centre` → Activités → Jeux rapides**. Les publications quotidiennes et leurs horaires restent inchangés.

## V10.54 — Migration effective vers les boutons NOX TV

Les actions **Statut, Diagnostic, Audit, Simulation, Catalogue** ne sont plus des commandes slash : elles sont disponibles via `/noxtv panneau` (boutons privés, permission Gérer le serveur). Les mentions de ces commandes ci-dessous sont historiques et ne doivent plus être utilisées comme instructions actuelles. Les autres commandes NOX TV restent disponibles.

# HORIZONS — Répertoire des commandes

Ce fichier est mis à jour à partir des commandes `app_commands` des extensions déclarées dans `bot.py`.
Il décrit les commandes présentes dans le code, **sans garantir leur synchronisation effective sur Discord** (elle dépend du démarrage, de la configuration et du chargement des extensions).
`/aide` affiche les commandes membres actuellement chargées ; `/aidestaff` est réservé à l’équipe et affiche les commandes staff.

## Commandes membres (catalogue extrait du code)

- `/affinites` — Panneau à boutons : activer, trouver, centres d’intérêt et désactiver.
- `/aide` — Consulter les commandes accessibles aux membres HORIZONS.
- `/anniversaire_supprimer` — Supprimer ton anniversaire enregistré.
- `/chercher` — Publier une annonce pour trouver quelqu'un avec qui faire une activité.
- `/compliment` — Offrir un mot positif à quelqu'un de la communauté.
- `/defi_collectif` — Voir le défi collectif en cours et sa progression.
- Fermeture des inscriptions : `/dashboard` → Rubriques du staff → Animations → « Fermer les inscriptions ».
- `/evenements` — Afficher les prochains événements HORIZONS.
- `/humeur` — Enregistrer ton humeur du jour en privé.
- `/idee` — Déposer anonymement une idée pour HORIZONS.
- `/jeux` — Découvrir les mini-jeux interactifs HORIZONS.
- `/ma_meteo` — Consulter ton humeur du jour en privé.
- `/mes_idees` — Consulter tes propositions envoyées à la boîte à idées.
- `/centre` → Mes activités → Saison — Consulter tes distinctions obtenues pendant les saisons.
- `/mes_succes` — Consulter tes succès HORIZONS débloqués.
- `/message_anonyme` — Publier un message sans afficher ton identité (si le salon est configuré).
- `/centre` → Mes activités → Saison — Consulter les trois étapes facultatives de la semaine.
- `/mon_passeport` — Consulter tes missions et ta progression du Passeport HORIZONS.
- `/parcours` — Découvrir et suivre ton Parcours des horizons.
- `/presentation` — Recevoir un rappel pour se présenter.
- `/profil` — Afficher les informations publiques d'un membre.
- `/proposer` — Transmettre une idée à l'équipe HORIZONS.
- `/question_du_jour` — Afficher une question pour lancer la conversation.
- `/rejoindre_defi` — Participer au défi collectif HORIZONS en cours.
- `/centre` → Mes activités → Saison — Rejoindre volontairement l'aventure de la saison HORIZONS.
- `/remercier` — Remercier publiquement un membre sur le mur de la solidarité.
- `/saison` — Découvrir la saison HORIZONS en cours et son objectif collectif.
- `/serveur` — Afficher les informations du serveur.
- `/signaler` — Transmettre discrètement un signalement à l'équipe.
- `/centre` → Mes activités → Saison — Valider une étape de ta saison en cours.
- `/valider_mission` — Valider une mission accomplie dans ton Passeport HORIZONS.
- `/xpjeux` — Consulter ta progression et tes XP Célestes.

## Commandes staff (catalogue extrait du code)

Accès selon le rôle et les permissions Discord. Les commandes de modération nécessitent une **prise de service active**.

- `/actualiser_rangs` — Recalculer les rangs honorifiques des membres (équipe).
- `/aidestaff` — Consulter les commandes et permissions de l'équipe HORIZONS.
- `/alerte_equipe` — Envoyer une alerte urgente à l'équipe HORIZONS.
- `/annonce` — Publier une annonce officielle dans un salon.
- `/avertir` — Enregistrer un avertissement pour un membre.
- `/avertissements` — Consulter les avertissements actifs d'un membre.
- `/bannir` — Bannir un membre du serveur.
- `/creer_defi` — Créer un nouveau défi collectif (équipe HORIZONS).
- `/dashboard` — Ouvrir le centre de commandement HORIZONS (staff).
- `/debannir` — Débannir un utilisateur à partir de son identifiant.
- `/export_structure` — Exporter en privé les salons, rôles et permissions du serveur.
- `/expulser` — Expulser un membre du serveur.
- `/giveaway creer` — Créer un giveaway avec une image facultative.
- `/givegratte` — Offrir des cartes à gratter à un membre (administration).
- `/horizons_dashboard` — Consulter les statistiques collectives HORIZONS (staff).
- `/idee_statut` — Mettre à jour le statut d'une idée (staff).
- `/note_membre` — Ajouter une note interne de modération à un membre.
- `/publier_guides_cercles` — Actualiser le panneau unique des Cercles HORIZONS.
- `/publier_roles` — Publier les panneaux de choix des rôles HORIZONS dans ce salon.
- `/purger` — Supprimer un nombre de messages dans le salon actuel.
- `/quiz_arreter` — Arrêter le quiz culturel en cours.
- `/quiz_lancer` — Lancer un quiz culturel à plusieurs manches (12 joueurs maximum).
- `/retirer_avertissement` — Clôturer un avertissement par son numéro.
- `/saison_clore` — Clôturer immédiatement la saison en cours (équipe uniquement).
- `/saison_lancer` — Lancer une nouvelle saison HORIZONS (équipe uniquement).
- `/service` — Déclarer le début ou la fin de ton service staff.
- `/tache_creer` — Créer une tâche pour un membre du staff.
- `/tache_statut` — Mettre à jour une tâche qui t'est attribuée (ou tâche staff si admin).
- Consultation des tâches : `/dashboard` → « 📋 Tâches » → filtre interactif (ancienne commande `/equipe taches` retirée en V10.57).
- `/timeout` — Mettre temporairement un membre en sourdine.
- `/untimeout` — Retirer le timeout d'un membre.

## Accès mixtes et interfaces interactives

- Fermeture des inscriptions : bouton du dashboard staff (service actif requis ; droits contrôlés dans le module Événements).
- `/affinites activer`, `/affinites desactiver`, `/affinites trouver` : sous-commandes membres.
- `/jeux` : menu Arcade (Morpion, Puissance 4, Memory, Code secret, Petit Bac, Bataille navale), avec modes solo, duel et collectif selon le jeu.
- Les panneaux, boutons et sélecteurs Discord complètent les commandes slash.

## Vérification des modules

- `cogs.smart_welcome` figure bien dans `EXTENSIONS` de `bot.py` ; `/premiers_pas` et `/accueil_bilan` sont donc prévus au chargement. Leur présence effective sur Discord dépend de la réussite du démarrage et de la synchronisation.

## Publications et tâches

Les horaires doivent être lus dans `cogs/publication_calendar.py`, `cogs/horizons_daily.py` et les modules de publication concernés ; ne pas utiliser les horaires de l’ancienne version de ce fichier comme source d’exécution.

## Configuration

- `.env` contient les paramètres locaux et doit rester privé.
- Le bot synchronise ses commandes au démarrage si `GUILD_ID` est configuré.
- Le rôle staff et les permissions Discord contrôlent l’accès aux commandes sensibles.
- La traduction dépend de `TRANSLATE_API_URL`.

## Actions par boutons (sans commande slash)
- `/jeux` : sélecteur des 6 jeux principaux et des 8 mini-jeux rapides / collectifs.
- Salon Arcade : panneau descriptif actualisé automatiquement.
- Salon Anniversaires : bouton permanent « Enregistrer / modifier mon anniversaire » ; formulaire JJ/MM avec année facultative.
- `/anniversaire_supprimer` : suppression de la date enregistrée.
- Si l'année est renseignée, le message automatique à 09 h affiche l'âge atteint.


## 🌌 Trésors du Ciel — panneau interactif

Dans le salon `🌌・trésors-du-ciel`, les membres utilisent désormais les **boutons permanents** du panneau : Gratter une carte, Ma collection, Constellations, Mon inventaire, Mes souvenirs, Découvrir une étoile (sélecteur), Échanger 20 poussières contre 1 fragment et Échanger 10 fragments contre 1 carte. Les huit anciennes commandes slash correspondantes sont retirées. `/givegratte` reste réservé aux administrateurs. Le panneau est mis à jour sans suppression toutes les deux heures et les actions sont privées.

La commande `/tester_publications` et son module ont été supprimés.


## Améliorations de finition

- `/dashboard` : bouton « Actualiser le bilan » en service.
- Animation collective du vendredi : bouton « Je participe » ; participation privée enregistrée en SQLite.
- Les propositions d’activités et défis quotidiens sont accessibles depuis le panneau « Que faire aujourd’hui ? », sans nouvelle commande slash.


## V7 — Activités accessibles sans commande slash

Dans le panneau permanent **🌅 Que faire aujourd’hui sur HORIZONS ?** :
- **Petits Bonheurs** : déposer ou remplacer un souvenir positif une fois par semaine. Contenu privé, non publié automatiquement.
- **Mystère du jour** : répondre en privé à une énigme tournante, une réussite maximum par jour.
- Les autres entrées du panneau (discuter, jouer, explorer, rencontrer, proposer, défi, événements, pause) restent disponibles.

Ces fonctions ne créent aucune nouvelle commande slash. `/aide` et `/aidestaff`
continuent de générer leurs listes à partir des commandes réellement chargées.


## V7 — Options du panneau (sans commande slash)

- **Rendez-vous surprise** : idée quotidienne privée pour proposer une activité.
- **Mon bocal** : lecture privée du petit bonheur de la semaine.
- **Petits Bonheurs** : dépôt ou remplacement volontaire de son message hebdomadaire.
- **Mystère du jour** : énigme à réponse privée.

## V7 — Étape 3 : interactions sans commande

- Panneau « Que faire aujourd’hui ? » → « Mes affinités » : choix privé de 1 à 3 centres d’intérêt, effacement possible.
- Aucune nouvelle commande slash. Les commandes `/aide` et `/aidestaff` restent inchangées.

## Activités accessibles par panneau (sans commande slash) — V7 étape 4

- **Constellation collective hebdomadaire** : progression de 5 étoiles à partir des participations au défi du jour, remise à zéro chaque lundi. Aucun classement individuel, aucune notification automatique.
- **Mystère du jour** : affiche le nombre total de résolutions du jour, sans publier les réponses ni l'identité des participants.
- **Mes affinités** : choix privé dans le panneau « Que faire aujourd'hui ? ». Attention : les commandes `/affinites` préexistantes ont un fonctionnement distinct ; une harmonisation est à prévoir après test, sans supprimer leurs données.

Ces fonctionnalités n'ajoutent aucune commande : `/aide` et `/aidestaff` ne changent pas.


## V7 — Les Liens du Ciel (étape 5)
Le menu « Mes affinités » du panneau renvoie aux commandes déjà existantes `/affinites activer`, `/affinites trouver` et `/affinites desactiver`. Aucune nouvelle commande. Le mur de solidarité conserve `/remercier`.


## Les Connexions du Ciel — panneau interactif V7

Le salon d'affinités existant (`AFFINITY_CHANNEL_ID`) affiche un embed permanent avec
**Activer mon profil**, **Trouver mes affinités**, **Mes centres d'intérêt** et
**Désactiver mon profil**. Les actions réutilisent les données et le moteur de
compatibilité de `/affinites` (au moins deux rôles compatibles, cinq suggestions
maximum), sans créer un second profil. Les réponses sont privées.

Les anciennes commandes `/affinites activer`, `/affinites trouver`,
`/affinites desactiver` restent disponibles pour compatibilité et figurent
dans `/aide` car elles sont encore enregistrées. Aucune commande staff ajoutée :
`/aidestaff` reste généré à partir des commandes réellement chargées.

## Panneaux permanents V7

- **Les Connexions du Ciel** : quatre boutons (activer, trouver, centres d'intérêt, désactiver) ; les commandes `/affinites` restent accessibles pour compatibilité.
- **Que faire aujourd'hui ?** : activités, défi quotidien, bocal, mystère, surprise et accès aux affinités.
- Les guides et panneaux utilisent les salons existants ; aucun salon supplémentaire n'est nécessaire.
- Les panneaux sont des interfaces Discord, **pas des commandes slash**.

## Contrôle documentaire

Le catalogue visible via `/aide` et `/aidestaff` est généré à partir de l'arbre des commandes effectivement chargé. Ce fichier reste un inventaire statique à comparer avec cet arbre après chaque mise à jour.

## V7 — Harmonisation finale des salons

Les six salons concernés par l'harmonisation des noms sont documentés dans `HARMONISATION_FINALE_V7.md`. Les nouveaux panneaux explicatifs d'activités et de défis ne nécessitent **aucune nouvelle commande slash**. `/aide` et `/aidestaff` conservent leur inventaire des commandes existantes.


## Panneaux interactifs (mise à jour audit du 09/11/2026)

Les salons **Paroles libres**, **Connexions du Ciel**, **Proposer un Cercle**, **Missions HORIZONS**, **Arcade HORIZONS**, **Trésors du Ciel**, **Météo des émotions**, **Boîte à idées** et **Éclats de reconnaissance** disposent de panneaux à boutons. Les commandes slash historiques restent disponibles pour compatibilité ; `/aide` et `/aidestaff` génèrent leurs listes depuis les commandes réellement chargées via `cogs/command_catalog.py`. Le salon **Confession** a été supprimé ; seul **Paroles libres** est conservé.

## Accès par boutons — salons fusionnés (V7.2)

- `💡・boite-a-idees` : proposer une idée et consulter ses idées ; `/idee`, `/mes_idees` restent des commandes de compatibilité.
- `🌐・cercles-horizons` : proposer un Cercle via formulaire, puis validation privée du staff et publication dans ce même salon. `/publier_guides_cercles` actualise le panneau.
- `🤝・activites-ensemble` : panneau interactif des activités ; `/chercher` reste accessible. Les initiatives sont désormais dirigées vers ce salon, sans publication automatique dans l'ancien.
- `💌・paroles-libres` : bouton d'écriture anonyme ; `/message_anonyme` reste accessible. Journal staff obligatoire et limite de deux publications sur dix minutes, persistante en SQLite.

Les commandes historiques ne sont pas supprimées tant que les boutons n'ont pas été vérifiés sur Discord. Les noms et permissions effectifs sont à contrôler après migration.

## V8.0 — Centre personnel

- `/centre` : ouvre un tableau de bord éphémère personnalisé (pseudo Discord, accueil selon l’heure locale, première visite ou retour après absence).
- Menu privé : Carte du Ciel, Lettres du Futur, Passerelles, Coffre, Capsules et activités. Les fonctionnalités non encore développées sont annoncées explicitement, sans progression fictive.
- Les anciennes commandes restent disponibles ; aucune nouvelle catégorie ni aucun nouveau salon n’est nécessaire.

### V8 — Suivi de présence
- `/evenement_presence numero membre` : l’organisateur ou le staff confirme une présence réelle après le début de l’événement. Nécessite une inscription « Je participe » ; confirmation unique persistante, sans attribution automatique d’étoile.

## 🌌 Découvrir le Centre HORIZONS (V8)

Le point d’entrée recommandé pour tous les membres est **`/centre`**. Il ouvre un tableau de bord personnel et privé, avec accueil par pseudo, Carte du Ciel et navigation vers les activités. Le Centre est présenté dans le message de bienvenue, le guide des premiers pas, le panneau de présentation, le panneau « Notre esprit » et `/aide`. Les commandes existantes restent utilisables.

### V8.2 — Lettres du Futur (Centre)
Dans `/centre` → **Mes Lettres du Futur**, le membre peut écrire une lettre à retrouver dans 7, 30 ou 90 jours, consulter les lettres arrivées à échéance et supprimer ses lettres. Trois lettres non ouvertes maximum ; aucun envoi automatique en MP à ce stade.

### V8.3 — Coffre des Horizons
`/centre` → « Mon Coffre des Horizons » affiche en privé le statut de la carte quotidienne, les cartes offertes, les 20 étoiles des Trésors du Ciel, les constellations, la poussière, les fragments et les souvenirs. Aucun tirage n’est réalisé depuis le Centre : pour gratter, utiliser le panneau existant de `🌌・trésors-du-ciel` ou `/gratter` dans ce salon. La Carte du Ciel V8 (étoiles de participation) reste distincte des 20 étoiles des Trésors.

Dans `/centre` → **Mes Capsules du Temps**, chaque membre peut créer une capsule privée à 30, 90 ou 180 jours, la consulter à échéance ou la supprimer. Les capsules collectives restent à développer.


### V8.4 — Capsules collectives
- `/centre` → Capsules du Temps : répondre volontairement à la question du mois, si ouverte.
- `/capsule_retirer numero` : retirer définitivement sa contribution, même après validation.
- `/capsule_reveler mois` : consulter en privé les contributions approuvées d'un mois (AAAA-MM), uniquement 90 jours après la question.
- Staff (permission Gérer le serveur) : `/capsule_question question`, `/capsule_attente`, `/capsule_moderer numero decision`.
- Aucune publication automatique dans un salon ; consentement explicite, modération préalable et contrôle de l'échéance.

### V8.5 — Passerelles du Ciel (première étape)
Dans `/centre` → **Mes Passerelles**, le membre peut choisir librement de 1 à 5 centres d'intérêt parmi huit thèmes. Le bot affiche uniquement un **nombre anonyme** d'autres membres volontaires partageant chaque thème. Aucune identité, aucun profil individuel et aucun message privé ne sont exposés. Le bouton « Quitter les Passerelles » efface les préférences et révoque le consentement. Le rapprochement réciproque entre deux personnes n'est **pas encore implémenté** ; il fera l'objet d'une étape distincte avec double accord.

### HORIZONS V8.5 — Passerelles du Ciel
Depuis `/centre` → « Mes Passerelles », le membre peut sélectionner jusqu'à cinq centres d'intérêt, proposer une invitation anonyme à un autre profil volontaire, répondre aux invitations reçues, annuler une invitation en attente ou quitter le dispositif. Les identités ne sont révélées qu'après acceptation ; aucun message privé automatique n'est envoyé. Les demandes et préférences sont supprimées lors du retrait. Les invitations sont consultées depuis `/centre` (pas de notification proactive).


### HORIZONS V8.6 — Mes activités et Main Tendue

- `/centre` → « Mes activités » présente les inscriptions récentes, leur état et le nombre de présences confirmées.
- `/evenement_presence` : l'organisateur ou le staff confirme une présence après le début de l'événement ; une première confirmation attribue l'étoile « Main Tendue » (une seule fois).
- Le simple clic « Je participe » n'attribue aucune étoile. Les annonces `/chercher` restent distinctes des événements organisés.


### HORIZONS V8.6 — Suivi personnel enrichi

- `/centre` → « Ma vie HORIZONS » : Cercles proposés ou suivis, statuts des idées, étapes de parcours et statistiques de l'Arcade.
- `/centre` → « Mes Passerelles » : suggestions de Cercles et d'événements selon les intérêts déclarés, sans révéler d'autres membres.
- `/centre` → « Ma météo privée » : historique facultatif des sept derniers jours, activation et effacement volontaire. L'effacement supprime aussi les entrées météo existantes du membre sur le serveur.
- Aucune nouvelle commande ni aucun nouveau salon.


## V8.7.5 — Vérification et renvoi du MP de bienvenue

- `/renvoyer_bienvenue membre:@pseudo` (staff) : renvoie le même guide à un membre possédant le rôle Membre, sans modifier son suivi SQLite.
- Les commandes sont restreintes au staff côté Python et au niveau Discord. Résultat visible uniquement par l’auteur (réponse éphémère). Les MP fermés sont signalés sans casser le bot.
- L’envoi automatique après validation de la charte reste inchangé.

## HORIZONS V8.8.9 — Régénérer le Regard du Jour

- `/regard_regenerer` : affiche une prévisualisation privée au staff, sans modification.
- `/regard_regenerer confirmer:Oui` : relance la collecte RSS, recalcule la sélection automatique, crée un nouveau sujet avec la présentation actuelle, puis supprime l'ancien sujet Discord **uniquement après** une publication réussie. Les articles validés explicitement par le staff sont conservés. Les autres dates, votes, XP et données SQLite restent intacts.
- Attention : les réponses des membres dans l'ancien sujet Discord seront supprimées avec celui-ci. Sauvegarder le fil avant de confirmer si nécessaire.
- Ne pas supprimer les bases SQLite ou le fichier `.env` de l'hébergement pendant le déploiement.

## 🌌 Chaos Cosmique — V9.0

Extension **optionnelle** (désactivée par défaut), avec base indépendante `data/chaos_cosmique.sqlite3`.

- `/cosmos observatoire` : consulter les jauges du monde (réponse privée).
- `/cosmos explorer` : découvrir l'Observatoire (réponse privée).
- `/cosmos canal salon:#nom-du-salon` : choisir un salon textuel (permission Gérer le serveur).
- `/cosmos activer actif:True` : activer le monde après configuration (permission Gérer le serveur).
- `/cosmos activer actif:False` : mettre en pause le monde.
- `/cosmos declencher` : publier une anomalie immédiatement pour la tester (une édition maximum par jour).

Une anomalie automatique est proposée après 18 h (Paris), au maximum une fois par jour, si aucune anomalie ne reste à résoudre. Trois boutons persistants déterminent la conséquence. La première réponse valide tranche pour l'ensemble du serveur. Les jauges sont sauvegardées et évoluent lentement une fois par jour. Les commandes sont sans effet sur les autres jeux, XP, salons et permissions.

**Sauvegarde :** préserver le dossier `data/` sur l'hébergement, notamment la nouvelle base `chaos_cosmique.sqlite3`. Ne jamais écraser `.env` ni les bases existantes lors du déploiement.

## 🌌 Chaos Cosmique — édition intégrale (V9.5)

**Installation différée :** aucune création de salon avant `/cosmos installer`. Le monde reste en pause par défaut.

**Administration (permission Gérer le serveur)**
- `/cosmos installer` : crée/réutilise la catégorie **🌌 CHAOS COSMIQUE** et cinq salons (Observatoire, Anomalies, Nox, Chroniques, Exploration), initialise le panneau sans activer les événements.
- `/cosmos activer actif:True` ou `False` : démarrer/mettre en pause l'univers.
- `/cosmos canal salon:#salon` : changer le salon des anomalies.
- `/cosmos declencher` : publier une anomalie manuellement (une maximum par date locale).
- `/cosmos actualiser` : actualiser le panneau de l'Observatoire.
- `/cosmos diagnostic` : état et paramètres du monde.

**Pour tous les membres**
- `/cosmos observatoire` : état du monde, privé.
- `/cosmos soigner action:` : parler, explorer, nourrir ou méditer avec Nox (chaque action une fois par personne et par jour).
- `/cosmos carte` : zones connues et conditions de déblocage.
- `/cosmos visiter lieu:` : fouiller une zone débloquée (une fois par lieu/personne/jour) et recevoir un objet.
- `/cosmos journal` : huit dernières traces du monde.
- `/cosmos explorer` : visite introductive de l'Observatoire.

**Fonctionnement :** 16 anomalies différentes, 3 décisions chacune, le premier clic valide détermine la conséquence, des jauges persistantes, quatre stades de Nox, six lieux progressifs, cinq chapitres, six objets à collectionner et une évolution quotidienne douce. Les boutons survivent aux redémarrages. Une seule anomalie automatique par jour après 18 h (Paris), si activée et aucune anomalie en cours. L'édition utilise exclusivement la base `data/chaos_cosmique.sqlite3`, sans modifier les données des autres modules.

**Sécurité :** le bot doit posséder `Gérer les salons` pour installer, `Envoyer des messages`, `Intégrer des liens` et `Lire l'historique` dans les salons. Ne supprime pas la base SQLite en mise à jour. Les créations sont idempotentes par nom, mais une catégorie ou des salons renommés manuellement ne seront pas reconnus par ce mécanisme. La publication est limitée pour éviter le spam ; l'absence de membres n'entraîne aucune punition.

### Chaos Cosmique — histoire officielle (V9.6)
- `/cosmos installer` : crée ou réutilise la catégorie cosmique et ses six salons, harmonise leur calligraphie, configure le salon histoire en lecture/réactions uniquement et publie l'embed avec son image. Peut être relancée après une installation V9.5.
- `/cosmos histoire` : republie l'histoire uniquement si le message officiel est absent (commande staff).
- Le salon `📖・𝓱𝓲𝓼𝓽𝓸𝓲𝓻𝓮-𝓭𝓾-𝓬𝓱𝓪𝓸𝓼` autorise les réactions mais interdit les messages et fils aux membres ordinaires.
- Image : `data/chaos_cosmique/histoire_chaos_cosmique.png`.

## 🌌 V10 INFINITY — accès membres par boutons

**Commande recommandée : `/nox`** (commande racine, sans préfixe `cosmos`).
Elle affiche le tableau de bord privé de Nox : Nourrir, Lui parler, Jouer, Se reposer, Explorer avec Nox, Carte du monde, Mon sac, Chroniques, Rencontre surprise.
Chaque soin est limité à une fois par jour et par membre ; le monde et la créature sont partagés à l'échelle du serveur.

**Salon histoire** : relancer `/cosmos installer` (staff) pour actualiser l'embed, l'image et installer les trois boutons permanents « Rencontrer Nox », « Explorer le monde », « État du cosmos ». L'ancienne publication est éditée sur place afin de conserver les réactions.

V10.55 : `/cosmos nox`, `/cosmos sac` et `/cosmos chroniques` sont remplacées par `/nox` et ses boutons. Les autres commandes `/cosmos` restent disponibles.

**Administration** : `/cosmos activer actif:True` pour éveiller le monde ; `/cosmos diagnostic` pour le vérifier ; `/cosmos declencher` pour une anomalie (limite quotidienne existante).

**Limites de cette version** : rencontres narratives quotidiennes, sans API IA ni dialogue libre ; le système de saisons complexes et les quêtes collectives annoncées comme idées futures ne sont pas encore des fonctions actives. Ne pas annoncer ces fonctions comme disponibles.

## V10.1 — Boutons supplémentaires, sans commandes supplémentaires
Dans `/nox` : **Mission du jour**, **Mes secrets**, **Mes rencontres**. Le bouton de mission propose de récupérer une récompense après avoir réalisé l'action de Nox demandée. Dans l'embed **Histoire du Chaos**, bouton **Mission du jour**. Les missions et les affinités sont individuelles; la créature reste collective. Les anciens slash commands sont conservés pour compatibilité.

### V10.2 — accès par boutons

Aucune nouvelle commande slash. Ouvrir `/nox`, puis utiliser les boutons **Saison actuelle**, **Rumeur du jour** ou **Expédition**. Dans le panneau Expédition, cliquer sur **Apporter un éclat**. Une contribution par membre et par jour, objectif collectif de 12 ; jouable seul. Ces boutons affichent leurs réponses en privé pour éviter le spam.

### V10.3 — Nouveaux boutons (aucune nouvelle commande)
- `/nox` → **Portail des paradoxes** : histoire personnelle du jour, trois décisions possibles, une seule enregistrée par jour.
- Salon Histoire → **Portail secret** : même expérience depuis l'accueil.
- `/cosmos installer` : met à jour l'embed d'accueil avec le bouton supplémentaire (à vérifier sur Discord réel).

## V10.4 — Intrigues croisées
Dans `/nox`, bouton **🎭 Intrigue des habitants** : un scénario quotidien met en scène plusieurs habitants, avec trois décisions possibles. Les conséquences modifient les jauges du monde, une affinité et le journal ; chaque membre ne peut valider qu'un choix par jour. Aucune commande supplémentaire ni modification de salon n'est nécessaire.

## V10.5 — Échos du destin

Aucune nouvelle commande slash. Dans `/nox`, bouton **✉️ Échos du destin** : affiche les conséquences de tes choix deux jours plus tard et les échos encore en préparation. Les retours restent personnels et éphémères ; aucune notification automatique ni mention.


### NOX TV (staff)
`/noxtv configurer salon:#salon` · `/noxtv activer actif:True/False` · `/noxtv tester`

- `/noxtv statut` — état de NOX TV et humeur de Nox (staff).

- `/noxtv votes message_id:<ID>` (staff) : récapitulatif des choix exprimés sous une publication NOX TV. Les membres votent directement avec les trois boutons du message, sans commande.

### V10.9 — NOX TV
Les votes des publications se ferment le lendemain ; le bot annonce le résultat dans le salon NOX TV. Aucune commande supplémentaire.


V10.10 : `/noxtv tester` crée désormais un scrutin de test traçable, clos le lendemain. Les verdicts changent selon la scène.

V10.12 : les tests NOX TV publiés dans un salon distinct conservent désormais leur salon pour le verdict du lendemain.

### NOX TV — V10.13
- `/noxtv configurer` : configuration historique de repli, conservée pour compatibilité.
- `/noxtv activer actif:true` : autorise les publications automatiques, qui sont réparties dans les salons indiqués par `COSMOS_CHANNEL_*`.
- `/noxtv tester` : publication de test dans le salon correspondant au type de visuel.
- Les verdicts sont envoyés dans `COSMOS_CHANNEL_CHRONIQUES` avec lien vers le message initial.

### V10.14 — NOX TV : contrôle qualité et catalogue
`/noxtv catalogue` affiche les identifiants des médias et leurs salons. `/noxtv tester scene:<identifiant>` permet de tester une scène précise sans consommer le quota automatique. Les réservations de publication sont libérées si le salon est absent ou incompatible, pour éviter de bloquer la journée. Publication automatique toujours désactivée par défaut.

V10.15 : `/noxtv tester scene:madame_paradoxe` et `/noxtv tester scene:gloups_experience`.

V10.16 : `/noxtv diagnostic` vérifie les salons et permissions NOX TV.

### NOX TV V10.17
`/noxtv catalogue` affiche les 13 médias disponibles ; `/noxtv tester scene:paradoxe_mardi_25` et `/noxtv tester scene:gloups_experience_547` permettent des tests ciblés.

### V10.18 — Deux scènes supplémentaires NOX TV
Deux nouveaux médias (Paradoxe : grève des horloges ; Gloups : fiole rebelle) et six verdicts narratifs. Catalogue : 15 médias. Version de développement, publication automatique toujours désactivée par défaut.


### V10.19 — NOX TV : étoile animée
Nouveau GIF `nox_etoile.gif` dans le salon Nox, trois verdicts dédiés. Le catalogue comporte 16 médias (14 PNG, 2 GIF). Publication automatique désactivée par défaut.

- `/noxtv apercu scene:<identifiant>` : aperçu privé d'une scène, sans publication ni vote.


### V10.22 — Correctifs NOX TV
- Aperçu privé : correction du traitement des médias manquants (plus de variables non définies), réponse Discord explicite.
- Chroniques : pas de repli vers un autre salon lorsque la destination des verdicts est invalide.
- Aucune migration destructive, aucun nouveau média annoncé.


## V10.23 — Fiabilisation du catalogue multimédia
Les médias sont désormais validés avant publication ou aperçu (chemin autorisé, format, taille maximale de 8 Mio, champs requis, identifiant unique). Un catalogue JSON illisible ne fait plus planter la sélection : aucune publication n’est envoyée. La galerie reste à 16 médias.

**V10.24 :** `/noxtv tester` ne modifie ni le calendrier ni l'historique de rotation automatique. Les publications de test peuvent toujours être votées et donner lieu à un verdict.

### NOX TV V10.25 — Audit de la galerie
`/noxtv audit` (staff) : vérifie le catalogue complet, les fichiers réellement accessibles, les GIF, les salons de destination et les trois verdicts de chaque scène, sans publier ni modifier SQLite.

### NOX TV V10.26 — Simulation sans publication
`/noxtv simulation` (staff) propose une scène en fonction de l’humeur de Nox, des deux dernières publications automatiques et du salon prévu. Aucun message public, vote, changement SQLite ou réservation de calendrier. Le tirage réel peut différer.

### V10.27 — Première animation originale du Canard Suprême
GIF `canard_matraque_anime.gif` : Coin-Coin agite sa cuisse de poulet dans l’Observatoire. Scène `canard_matraque_anime` destinée au salon Anomalies, trois verdicts dédiés. Aucun changement de commande ou de base de données.

V10.28 : `/noxtv apercu scene:grille_pain_panique_anime` pour prévisualiser le nouveau GIF.


V10.31 : `canard_matraque_anime` et `nox_faim_anime` disponibles via les commandes NOX TV de prévisualisation et de test.

V10.32 : `/noxtv bilan` (staff) — statistiques privées en lecture seule.

### V10.33
Aucune nouvelle commande : correction des tests de validation de la galerie animée.

### V10.35
Quatre nouvelles scènes consultables via `/noxtv catalogue` et `/noxtv apercu`.

V10.36 : `/noxtv catalogue`, `/noxtv apercu`, `/noxtv audit` couvrent les 30 scènes.


### V10.37 — Correctif audit NOX TV
Ajout des trois verdicts de `nox_faim_anime` (GIF de Nox affamé). Aucune modification des médias, salons, horaires ni paramètres. Relancer `/noxtv audit` après déploiement : résultat attendu 30/30, zéro anomalie.


## Migration V10.56
- `/capsule_retirer` : remplace par le selecteur **Retirer une contribution collective** dans `/centre` > Capsules.
- Les autres commandes restent disponibles en attendant leur migration et leurs tests.


## Migration V10.58 — panneaux consolidés

- `/dashboard` → **Statistiques collectives** : remplace l’ancien accès au tableau analytique HORIZONS (déjà intégré).
- `/dashboard` → **NOX TV** → **Bilan** : remplace `/noxtv bilan`.
- `/dashboard` → **NOX TV** : remplace `/noxtv panneau`.
- `/dashboard` → **Prendre/Terminer mon service** : remplace `/equipe service`.
- Les anciens libellés de commandes mentionnés plus haut sont historiques et ne doivent plus être présentés comme commandes disponibles.


### V10.59 — Saisons depuis le Centre
Les actions Rejoindre, Voir les étapes, Valider une étape et Mes distinctions sont disponibles dans `/centre` → Mes activités → Saison. Leurs anciennes commandes slash ont été retirées. `/saison` reste disponible.


### Migration V10.61 — Progression personnelle
- `/centre` → **Ma vie** → **Ma progression** : rang honorifique, Parcours des horizons et badges.
- Les anciennes commandes `/mon_parcours` et `/parcours_badges` sont remplacées par ce menu. `/parcours` reste un raccourci.


## V10.65 — Affinités
Les anciennes sous-commandes `/affinites activer`, `/affinites desactiver` et `/affinites trouver` sont remplacées par `/affinites` et ses quatre boutons (activation, recherche, centres d’intérêt, désactivation). Le panneau permanent conserve les mêmes actions. `/chercher` reste disponible pour les annonces d’activité.

### Migration V10.66 — Regardboard
- `/regard diagnostic` et `/regard selection` sont remplacées par les boutons **Diagnostic** et **Articles à valider** de `/dashboard` → **Regardboard**.
- Accès réservé au staff en service ; les autres commandes Regard restent disponibles en attendant leur migration avec des formulaires adaptés.


### Migration V10.70 — Quiz culturel
Les commandes slash `/quiz_lancer` et `/quiz_arreter` sont remplacées par les boutons **Lancer quiz** et **Arrêter quiz** dans `/dashboard` → **Event**. Les membres participent toujours depuis les boutons du message de quiz. Accès staff en service requis pour le tableau de bord.


## Migration V10.72 — Regard du Jour
- `/regard proposer` : remplacée par `/centre` → Regard du Jour → **Proposer un article**.
- `/regard points` : remplacée par `/centre` → Regard du Jour → **Mes points Regard**.
- Les autres commandes Regard non migrées restent disponibles.


### Migration V10.73 — Regardboard
Les commandes `/regard collecter` et `/regard ajouter` sont désormais accessibles dans `/dashboard` → Regardboard, via les boutons **Collecter les liens** et **Ajouter un article**. Les traitements et permissions sont conservés.
