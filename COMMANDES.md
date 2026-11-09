# HORIZONS — Répertoire des commandes

Ce fichier est mis à jour à partir des commandes `app_commands` des extensions déclarées dans `bot.py`.
Il décrit les commandes présentes dans le code, **sans garantir leur synchronisation effective sur Discord** (elle dépend du démarrage, de la configuration et du chargement des extensions).
`/aide` affiche les commandes membres actuellement chargées ; `/aidestaff` est réservé à l’équipe et affiche les commandes staff.

## Commandes membres (catalogue extrait du code)

- `/affinites activer` — Autoriser les suggestions d'affinités amicales.
- `/affinites desactiver` — Retirer ton profil des suggestions d'affinités.
- `/affinites trouver` — Trouver des membres volontaires qui partagent tes centres d'intérêt.
- `/aide` — Consulter les commandes accessibles aux membres HORIZONS.
- `/anniversaire_supprimer` — Supprimer ton anniversaire enregistré.
- `/blague` — Découvrir une blague HORIZONS.
- `/chercher` — Publier une annonce pour trouver quelqu'un avec qui faire une activité.
- `/compliment` — Offrir un mot positif à quelqu'un de la communauté.
- `/defi_collectif` — Voir le défi collectif en cours et sa progression.
- `/devinette` — Jouer à une devinette HORIZONS.
- `/evenement_fermer` — Fermer les inscriptions d'un événement.
- `/evenements` — Afficher les prochains événements HORIZONS.
- `/humeur` — Enregistrer ton humeur du jour en privé.
- `/idee` — Déposer anonymement une idée pour HORIZONS.
- `/jeux` — Découvrir les mini-jeux interactifs HORIZONS.
- `/ma_meteo` — Consulter ton humeur du jour en privé.
- `/mes_idees` — Consulter tes propositions envoyées à la boîte à idées.
- `/mes_recompenses_saison` — Consulter tes distinctions obtenues pendant les saisons.
- `/mes_succes` — Consulter tes succès HORIZONS débloqués.
- `/message_anonyme` — Publier un message sans afficher ton identité (si le salon est configuré).
- `/missions_saison` — Consulter les trois étapes facultatives de la semaine.
- `/mon_parcours` — Consulter ton rang honorifique HORIZONS.
- `/mon_passeport` — Consulter tes missions et ta progression du Passeport HORIZONS.
- `/parcours` — Découvrir et suivre ton Parcours des horizons.
- `/parcours_badges` — Consulter les thèmes accomplis et tes badges HORIZONS.
- `/ping` — Vérifier si le bot HORIZONS répond.
- `/presentation` — Recevoir un rappel pour se présenter.
- `/profil` — Afficher les informations publiques d'un membre.
- `/proposer` — Transmettre une idée à l'équipe HORIZONS.
- `/question_du_jour` — Afficher une question pour lancer la conversation.
- `/rejoindre_defi` — Participer au défi collectif HORIZONS en cours.
- `/rejoindre_saison` — Rejoindre volontairement l'aventure de la saison HORIZONS.
- `/remercier` — Remercier publiquement un membre sur le mur de la solidarité.
- `/saison` — Découvrir la saison HORIZONS en cours et son objectif collectif.
- `/serveur` — Afficher les informations du serveur.
- `/signaler` — Transmettre discrètement un signalement à l'équipe.
- `/ticket_fermer` — Fermer le ticket actuel.
- `/ticket_ouvrir` — Ouvrir un espace privé pour contacter l'équipe.
- `/traduire` — Traduire un texte avec le service configuré par HORIZONS.
- `/valider_etape_saison` — Valider une étape de ta saison en cours.
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
- `/evenement_creer` — Créer un rendez-vous communautaire HORIZONS.
- `/export_structure` — Exporter en privé les salons, rôles et permissions du serveur.
- `/expulser` — Expulser un membre du serveur.
- `/giveaway annuler` — Annuler un giveaway en cours.
- `/giveaway creer` — Créer un giveaway avec une image facultative.
- `/giveaway reroll` — Effectuer un nouveau tirage parmi les participants.
- `/givegratte` — Offrir des cartes à gratter à un membre (administration).
- `/horizons_dashboard` — Consulter les statistiques collectives HORIZONS (staff).
- `/idee_statut` — Mettre à jour le statut d'une idée (staff).
- `/note_membre` — Ajouter une note interne de modération à un membre.
- `/publier_guides_cercles` — Publier ou actualiser les deux guides permanents des Cercles HORIZONS.
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
- `/taches` — Consulter les tâches de l'équipe staff.
- `/timeout` — Mettre temporairement un membre en sourdine.
- `/untimeout` — Retirer le timeout d'un membre.

## Accès mixtes et interfaces interactives

- `/evenement_fermer` : fermeture par le créateur de l’événement ou l’équipe selon les contrôles du module.
- `/ticket_fermer` : fermeture par le membre dans son ticket ou l’équipe habilitée.
- `/affinites activer`, `/affinites desactiver`, `/affinites trouver` : sous-commandes membres.
- `/giveaway creer`, `/giveaway annuler`, `/giveaway reroll` : sous-commandes staff.
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
