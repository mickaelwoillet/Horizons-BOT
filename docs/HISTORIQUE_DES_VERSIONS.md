## V8.8.4 — Le Regard du Jour : édition communautaire, sommaire, suivi, bilan hebdomadaire, XP et sécurité

Voir `NOTES_V8_8_4_REGARD_DU_JOUR.md`.

# HORIZONS — Historique des améliorations précédentes

Ce document conserve les notes de versions antérieures, sans suppression de contenu.


---

## Archive : ETAT_JEUX_CONSTELLATIONS.md

# HORIZONS — État de l'Arcade et des constellations

Audit du code du ZIP fourni le 9 novembre 2026. « Présent » signifie implémenté dans les sources, **pas validé sur le serveur Discord**.

## Arcade — déjà présent

- Menu `/jeux` : Morpion (solo contre IA / duel), Puissance 4 (duel), Memory (solo), Code secret (solo), Petit Bac (collectif), Bataille navale (duel et grilles privées).
- Autres mini-jeux slash : `/de`, `/pileface`, `/nombre_mystere`, `/quizjeu`, `/anagramme`, `/enigme`, `/reflexe`, `/arcade_collectif`.
- XP Célestes, historique, statistiques, succès, missions hebdomadaires et récupération des récompenses via `/xpjeux` et ses interfaces.
- Soirée Arcade collective, invitations, abandons et gestion des manches dans les vues interactives.
- Présentation automatique du salon Arcade par une tâche périodique de 2 heures.
- Tests unitaires présents : `tests/test_arcade_games.py` et `tests/test_arcade_progress.py`.

## Trésors célestes — déjà présent

- Carte à gratter quotidienne + cartes offertes (`/gratter`, `/givegratte`).
- Récompenses pondérées : pensée 40 %, poussière 25 %, XP 15 %, étoile 12 %, fragment 7 %, surprise 1 %.
- Collection de 20 étoiles réparties en 5 constellations de 4 étoiles.
- Échange de 20 poussières contre 1 fragment ; de 10 fragments contre 1 carte offerte.
- Protection contre les séries de doublons d'étoiles : garantie d'une étoile manquante au-delà du seuil codé de 12 doublons consécutifs lors d'un tirage d'étoile.
- Rôles automatiques par constellation et rôle final des 20 étoiles, si leurs identifiants sont configurés et les permissions du bot suffisantes.
- Six souvenirs illustrés (un par constellation et un final) et commandes de consultation de collection / inventaire / souvenirs.
- Présentation automatique du salon Trésors célestes par une tâche périodique de 2 heures.
- Ressources graphiques de cartes, récompenses et souvenirs présentes dans `data/assets/celestial/`.

## À terminer / à valider avant de considérer ces modules achevés

1. **Tests sur Discord en conditions réelles** : menus, boutons, modales, parties en solo, duels, jeux collectifs, abandons, délais, messages privés et salons configurés. Les tests statiques ne prouvent pas le fonctionnement en production.
2. **Vérification des rôles de constellation** : identifiants, hiérarchie des rôles Discord, permission Gérer les rôles et attribution automatique aux membres concernés.
3. **Scénarios de collection** : carte quotidienne (limite d'une par jour), cartes offertes, tous les types de récompenses, conversions de monnaies, doublons, protection au 12e doublon, cinq constellations et collection finale.
4. **Résistance aux redémarrages** : vérifier le comportement des parties interactives en cours et des vues Discord après redémarrage. Les données persistantes en SQLite ne garantissent pas que chaque partie interactive reprenne automatiquement.
5. **Tests de concurrence** : plusieurs joueurs, clics simultanés, double validation, invitations expirées et droits d'accès aux vues privées.
6. **Couverture automatisée des trésors célestes** : ajouter des tests dédiés à la distribution, aux échanges, aux souvenirs et aux rôles ; les tests unitaires existants ciblent principalement les jeux et leur progression.
7. **Validation des présentations automatiques** : salons Arcade / Trésors, périodicité et absence de doublons après redémarrage.
8. **Équilibrage communautaire** : observer l'attribution réelle d'XP, les récompenses et la vitesse de complétion des 20 étoiles avant de modifier les probabilités.

## Mise à jour du centre d'aide (même livraison)

- `/aide` : uniquement les commandes membres réellement chargées, présentées par catégories et avec paramètres.
- `/aidestaff` : accès réservé au staff reconnu par le tableau de bord ; commandes d'équipe, paramètres et indications de permissions.
- `COMMANDES.md` : répertoire actualisé d'après les extensions déclarées dans `bot.py`.
- Modules `smart_welcome` et `publication_tests` : présents dans les sources, **non déclarés dans `EXTENSIONS`**, donc leurs commandes ne sont pas chargées au démarrage standard. Ils n'ont pas été activés dans cette livraison.


Mise à jour du 09/11/2026 : commandes Trésors célestes regroupées dans un panneau interactif persistant ; /tester_publications supprimée. Tests Discord à réaliser ultérieurement.


---

## Archive : AMELIORATIONS_INTERACTIONS_V5.md

# HORIZONS — Fiabilisation des interactions V5

Cette version reprend l'archive cumulative V4, sans modifier les commandes slash.

## Propositions d'activité
Le formulaire du panneau « Que faire aujourd'hui ? » limite chaque membre à deux propositions récentes **encore ouvertes et non expirées** dans les six dernières heures. Les propositions fermées ou expirées ne bloquent plus la création. Le panneau utilise toujours la publication et les boutons du module Expériences. La limite ne s'applique qu'au formulaire de ce panneau, et non à la commande historique `/chercher`.

## Panneau permanent
Le message est identifié par son ID dans `bot_settings` et une signature dans son embed. Il est réutilisé après redémarrage, et modifié uniquement lorsque son titre, son texte ou ses composants doivent être restaurés. La vérification se déroule toutes les six heures.

## Participations
Le défi du jour utilise la table SQLite `today_challenge_participation` avec une clé unique (serveur, jour, membre). Une deuxième participation le même jour n'ajoute pas de ligne. Le redémarrage ne supprime pas les données **si le fichier SQLite `data/` est conservé**.

## Contrôles
`python -m unittest discover -s tests -p test_today_hub_integrity.py -v`

Les contrôles de code ne remplacent pas les essais Discord. En particulier, l'absence de doublon lors de plusieurs démarrages simultanés et la disponibilité des salons cibles restent à confirmer en environnement réel.


---

## Archive : AUTONOMIE_ACCUEIL_V2.md

# HORIZONS — Accueil autonome V2

## Livré dans cette version
- Activation de `cogs.smart_welcome` dans `bot.py` (module présent mais non chargé auparavant).
- Envoi d’un accueil guidé lors de l’arrivée d’un membre, avec lien vers la charte et bouton persistant « Découvrir HORIZONS ».
- Le bouton ouvre en privé les liens utiles **uniquement après** validation du rôle Membre.
- Après validation de la charte : guide privé envoyé une seule fois (si les messages privés sont ouverts).
- Un seul rappel facultatif au bout de 36 heures en l’absence d’interaction ; pas de relance répétée.
- Suivi des étapes dans SQLite (`onboarding_progress`), avec migration non destructive.
- `/premiers_pas` reste disponible en solution de secours ; `/accueil_bilan` reste réservé aux personnes ayant Gérer le serveur.
- Correction : aucune relance n’est marquée comme envoyée lorsque le serveur n’est pas accessible dans le cache du bot.

## À vérifier à l’installation
- Les permissions d’envoyer des messages dans le salon de bienvenue et de lire l’historique.
- Les identifiants de salon/rôles dans `.env` et la position du rôle du bot.
- L’intention **Members** (événements d’arrivée) et **Message Content** si le suivi de participation est souhaité.
- Le comportement des messages privés (ils peuvent être fermés) et la présence d’autres messages de bienvenue : supprimer les doublons éventuels après installation.

## Étapes suivantes conseillées
1. Ajouter un panneau permanent « Que faire aujourd’hui ? » (animations, événements, activités) avec réponses privées.
2. Donner aux membres un moyen d’opter pour ou contre les rappels privés ; réduire encore les sollicitations non demandées.
3. Vérifier la robustesse de l’anti-doublon après redémarrage et les interactions de boutons existants.
4. Mettre en place sauvegardes automatiques, surveillance des pannes et relais staff pour les situations sensibles.
5. Tester l’accueil avec un compte secondaire, puis les fonctions multi-membres lorsque cela sera possible.

## Limites
Contrôles statiques uniquement : pas de test en connexion réelle à Discord. Le bot facilite les échanges, mais les sanctions graves, urgences et situations sensibles nécessitent des responsables humains.


---

## Archive : AUTONOMIE_HORIZONS.md

# HORIZONS — Autonomie et continuité (audit de travail)

## Modifications apportées
- Panneau Arcade stable : édition du message enregistré, récupération par marqueur en cas de restauration de la base, sans suppression de messages. Les anciens panneaux sans marqueur ne sont pas effacés automatiquement.
- Catalogue des commandes du staff : une seule source de vérité (`command_catalog.py`) pour `/aidestaff` et les panneaux du salon staff. Les panneaux du staff sont désormais permanents et mis à jour en place, sans repost hebdomadaire.
- Suppression effective de `cogs/publication_tests.py` et correction des tests de cohérence : `/tester_publications` n'est plus fourni.

## Priorités pour une communauté sans présence quotidienne du fondateur
1. **Continuité technique** : hébergement permanent, redémarrage automatique du processus, sauvegardes régulières de `data/` et de `.env` dans un coffre sécurisé distinct, supervision des échecs et des tâches programmées.
2. **Relais humains** : au moins deux personnes de confiance disposant des permissions adaptées, avec procédure d'escalade et limites explicites. Un bot ne peut pas remplacer un humain dans une situation de crise, de harcèlement complexe ou de danger immédiat.
3. **Accueil et interactions** : parcours guidé par boutons, questions contextuelles et invitations facultatives à participer, sans messages privés non sollicités ni relances insistantes.
4. **Modération** : automatiser le tri et la journalisation ; conserver la décision humaine pour les sanctions graves et les signalements sensibles.
5. **Jeux** : tests unitaires des règles, persistance des sessions lorsque possible, et gestion des interactions expirées ; tester à plusieurs dès que des membres seront présents.
6. **Vie communautaire** : contenu renouvelé, fréquence adaptable à l'activité réelle, éviter les publications en cascade dans un salon vide.
7. **Transparence** : le bot doit se présenter comme un assistant automatisé HORIZONS, jamais comme le fondateur ni comme une personne réelle.

## Incohérences et limites encore visibles
- `cogs/smart_welcome.py` est présent mais absent de `EXTENSIONS` : vérifier s'il s'agit d'un ancien module ou d'une fonctionnalité volontairement désactivée avant toute activation.
- Les anciens messages hebdomadaires du catalogue staff et les anciens panneaux Arcade déjà présents sur Discord ne sont pas supprimés à distance par cette mise à jour.
- Les boucles de publication s'exécutent sur une instance de bot ; une exécution simultanée de plusieurs instances peut provoquer des doublons. Prévoir un verrouillage distribué si l'hébergement change.
- Les salons et rôles doivent être vérifiés sur le serveur réel ; les tests locaux ne valident ni permissions ni interactions réseau.
- L'absence prolongée du fondateur nécessite une procédure d'accès d'urgence et de renouvellement des secrets, indépendante du code du bot.

## Vérifications différées
- Vérifier `/aide` et `/aidestaff` avec comptes membre / modérateur / administrateur.
- Vérifier l'édition des panneaux Arcade, Trésors et anniversaires après redémarrage.
- Tester les jeux multijoueurs et les rôles célestes à plusieurs.
- Vérifier que les anciennes commandes supprimées ont disparu de la synchronisation Discord.


---

## Archive : AMELIORATIONS_EN_COURS.md

# HORIZONS — Améliorations en cours (9 novembre 2026)

## Implémenté dans cette version de travail
- Huit anciennes commandes slash de l’Arcade déplacées dans le sélecteur `/jeux` : dé, pile ou face, nombre mystère, quiz rapide, anagramme, énigme, réflexe et défi collectif.
- Les six jeux principaux restent présents ; le sélecteur propose maintenant 14 entrées.
- Les défis collectifs disposent d’un second menu pour choisir parmi sept variantes.
- Embed du salon Arcade mis à jour : aucune instruction obsolète invitant à utiliser les commandes retirées.
- Anniversaires : panneau avec bouton permanent et formulaire (JJ/MM + année facultative).
- `/anniversaire_definir` retirée ; `/anniversaire_supprimer` conservée.
- Si l’année est renseignée, l’âge atteint est affiché dans le message automatique.
- Migration SQLite non destructive de `birth_year`.
- `COMMANDES.md` et catalogue d’aide mis à jour pour retirer les anciennes commandes.
- Tests statiques adaptés : 49 Python, 41 JSON, 34 extensions, 87 commandes slash.

## À vérifier lorsque le bot pourra être lancé sur Discord
- Synchronisation Discord des commandes retirées (les commandes globales anciennes peuvent rester visibles jusqu’à propagation).
- Bouton permanent du salon anniversaire, modal et âge affiché.
- Déclenchement de chacun des mini-jeux depuis le sélecteur et des défis collectifs.
- Publication / mise à jour du panneau Arcade et des guides permanents.

## Incohérences et pistes de qualité
- Le ZIP source contient `.git` et `.venv` (volumineux et propres à la machine) ; les conserver dans le ZIP de travail tant que leur suppression n’a pas été autorisée.
- L’ancien panneau hebdomadaire d’anniversaires peut subsister dans le salon : ne pas supprimer d’autres messages sans vérifier leur marqueur.
- Les tests statiques ne remplacent pas les tests d’interactions réelles.


Mise à jour du 09/11/2026 : commandes Trésors célestes regroupées dans un panneau interactif persistant ; /tester_publications supprimée. Tests Discord à réaliser ultérieurement.

Mise à jour autonomie : panneau Arcade édité en place ; catalogue staff permanent unifié avec /aidestaff ; suppression réelle du module /tester_publications ; voir AUTONOMIE_HORIZONS.md.


---

## Archive : INTERACTIONS_COLLECTIVES_V4.md

# HORIZONS — Interactions collectives V4

## Modifications

- Ajout de « 🌱 Défi du jour » au menu permanent « Que faire aujourd'hui ? ».
- Sept défis bienveillants, un par jour de semaine, sans compétition et sans obligation.
- Un bouton privé « J'ai participé » permet de contribuer au compteur collectif ; une seule contribution par membre et par jour, conservée en SQLite.
- Aucun message public, mention ou sollicitation automatique ne découle d'une participation.
- Protection contre les propositions répétées : maximum deux annonces d'activité encore ouvertes créées dans les six dernières heures via le formulaire du panneau.
- Réduction des éditions inutiles du panneau : l'embed n'est réédité que lorsque son texte change.

## Comportement et limites

- Le bouton est une **déclaration volontaire**, sans preuve ni vérification de la réalisation du défi.
- Le compteur est informatif, et n'accorde aucun XP ou récompense : l'objectif est de créer des échanges humains, pas une course aux clics.
- Le défi change avec le jour local du serveur. Le panneau est rafraîchi par le cycle de maintenance déjà présent (toutes les six heures) ; le défi privé affiche toujours le jour courant.
- Les données du compteur sont stockées dans `today_challenge_participation` dans la base SQLite existante.
- Le bot doit être redémarré avec la nouvelle version pour appliquer les changements ; aucune modification n'a été faite sur Discord depuis cette archive.

## Vérifications à réaliser à l'installation

1. Ouvrir le salon « aujourd'hui sur HORIZONS », choisir « Défi du jour ».
2. Cliquer « J'ai participé » deux fois : le compteur ne doit augmenter qu'une seule fois.
3. Tester le lendemain : un nouveau défi et une nouvelle participation doivent être disponibles.
4. Vérifier qu'aucune notification publique n'a été émise.
5. Vérifier le formulaire « Proposer une activité » et sa limite anti-spam.
6. Vérifier la reprise du panneau après redémarrage sans création de doublon.

## Prochaines étapes recommandées

1. **Fiabilité** : sauvegardes automatiques SQLite, vérification de restauration et alertes de fonctionnement.
2. **Continuité humaine** : rôles de relais, transmission des incidents et consignes de gestion des absences du fondateur.
3. **Qualité des interactions** : tests Discord réels des boutons et permissions, puis ajustements selon les retours des membres.


---

## Archive : INTERACTIONS_COMMUNAUTAIRES_V3.md

# HORIZONS — Interactions communautaires V3

## Nouveautés du panneau « Que faire aujourd'hui ? »

- Le panneau affiche une idée du jour différente selon le jour de la semaine. Il actualise le même message, sans ping et sans message quotidien supplémentaire.
- Nouveau choix « ✨ Proposer une activité » dans le sélecteur. Il ouvre une sélection de sept types d'activité, puis un formulaire de précision facultative (300 caractères maximum).
- La proposition réutilise le système existant `Experiences.chercher` : annonce de six heures dans le salon de recherche, bouton « Ça m'intéresse », suivi SQLite, expiration et réponse privée. Aucune commande slash supplémentaire.
- Le choix « 🤝 Rencontrer » conserve l'accès aux propositions déjà ouvertes.
- Les vérifications du rôle membre et de la charte sont conservées. Pas de mention `@everyone`, pas de sollicitation privée non demandée.

## Choix de conception

Aucune animation automatique n'est déclenchée selon le nombre de membres connectés : la présence Discord est imparfaite et une animation forcée risquerait de rendre le serveur artificiel. Le bot facilite des invitations **volontaires**, réutilisant les outils éprouvés du projet.

## Contrôles à effectuer plus tard

1. Vérifier les sept choix d'activité et la validation du formulaire.
2. Vérifier le message « Ça m'intéresse » et l'expiration après six heures.
3. Vérifier le comportement après redémarrage.
4. Vérifier le rendu de l'idée du jour et le renouvellement sans doublons.
5. Vérifier les droits d'accès au salon de propositions.

## Limites

Les contrôles de syntaxe sont réussis. Aucune connexion Discord ni essai réel d'interaction n'a été effectué. Le module dépend du chargement de `cogs.experiences` et de la configuration du salon de recherche.


### V8 — Découvrabilité du Centre (travail cumulatif)
- Mise en avant de `/centre` dans cinq points d’entrée existants, sans nouveau salon ni publication automatique supplémentaire.
- Textes des embeds d’accueil, premiers pas, présentation, Notre esprit et catalogue des commandes actualisés.
