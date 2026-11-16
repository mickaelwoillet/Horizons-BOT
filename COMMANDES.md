# Commandes et fonctionnalités — HORIZONS

> Ce document décrit les panneaux et modules. Le catalogue `/aide` et `/aidestaff` est construit dynamiquement à partir des commandes effectivement chargées.

### NOX — vie spontanée (V10.85.7)

- `/nox` → Administration → Vie spontanée (salon et activation) : administrateur ; active ou suspend les interventions humoristiques spontanées de NOX dans le salon choisi. Par défaut désactivé. Maximum une intervention toutes les 22 h entre 9 h et 22 h (Europe/Paris). Webhook NOX requis.
- Les 160 dialogues sont dans `data/nox/dialogues_vie.json`. Ils ne lisent aucun message privé ou public et ne déclenchent pas de mentions.

### NOX V10.85.8 — Réactions et rythme
- Les six boutons du Refuge disposent chacun de 12 réponses originales (72 au total), envoyées uniquement à la personne qui a cliqué, sans spam public.
- Les interventions de besoin (`/nox` → Administration → Besoins de NOX) et de vie (`/nox` → Administration → Vie spontanée) s’espacent mutuellement d’au moins 2 heures. Leurs limites individuelles restent en vigueur.
- Les répliques sont modifiables dans `data/nox/reactions_soins.json`.

### NOX — réactions aux événements (V10.85.9)

`/nox` → Administration → Événements (anniversaires et quiz) — administrateurs uniquement. Désactivé par défaut. Anniversaire : NOX remplace le message habituel avec retour automatique au message classique si webhook indisponible. Quiz : réaction optionnelle après classement, une fois par session.

### V10.85.10 — Surprises collectives NOX
`/nox` → Animations → Surprise (administrateur) : choisir parmi 4 thèmes (absurdité, question, mini-défi, douceur) et un salon. NOX publie via webhook ; pas de publication automatique. 32 répliques dans `data/nox/surprises_collectives.json`.

### Aventures collectives de NOX (V10.85.11)
- `/noxaventure action:lancer salon:#salon` : administrateur, lance une aventure avec 3 boutons de vote.
- `/noxaventure action:conclure` : administrateur, clôture et publie le résultat (votes persistants, un vote par membre modifiable).
- Une aventure active par serveur ; votes pendant 30 minutes ; aucun envoi automatique.

### Distinctions NOX (V10.85.13)
- `/noxtitres` : membre, affiche en privé les distinctions symboliques calculées à partir des soins du Refuge. Rôles Discord attribués si installés, aucun XP.

- `/nox` → Administration → Créer les rôles : administrateur, crée les sept rôles de NOX sans doublons.
- `/nox` → Administration → Synchroniser rôles : administrateur, attribue les rôles acquis aux membres déjà contributeurs (100 par appel, paramètre `debut` pour les suivants).\n
- `/noxmission lancer [salon]` : lance une mission collective de NOX (administrateurs).
- `/noxmission conclure` : clôture la mission et publie son bilan (administrateurs).

- `/noxquotidien salon:#salon actif:true|false` (administrateur) : 12 publications de NOX par jour, de 10 h à 22 h 50 (Europe/Paris), dans le salon choisi. Pas de rattrapage après interruption.

### NOX : publications illustrées
`/noxquotidien` : 12 publications entre 10 h et 22 h 50, dont 6 avec une image directement liée au texte. Le bot doit pouvoir joindre des fichiers.

V10.85.17 : `/noxquotidien` répartit les 12 créneaux entre humour, questions, aventures, entraide, défis, discussions, bienveillance et soirée ; six sont illustrés.

### Réponses spontanées NOX (V10.85.18)
NOX peut répondre occasionnellement aux réponses directes à ses 12 publications quotidiennes : 35 % de chance, maximum 3 réactions par serveur et par jour, 20 minutes minimum entre deux réponses, et une seule par membre et par jour. Entre 10 h et 23 h (Paris). Aucun contenu des messages des membres n’est lu ni conservé. Aucune nouvelle commande.

### V10.85.19 — Sondages interactifs de NOX
Deux des 12 publications quotidiennes (11h10 et 18h10) sont des mini-sondages à trois boutons. Un vote par membre et par sondage, modifiable jusqu’à 23h ; résultats provisoires privés. Aucun message quotidien supplémentaire, aucune nouvelle commande.

### NOX — défis quotidiens (V10.85.20)
À **15 h 50**, NOX publie un défi communautaire à la place du créneau textuel existant. Bouton persistant « Je relève le défi ! », une inscription par membre et par jour, clôture à 23 h. Aucun nouveau salon, aucune commande et aucun XP.

### NOX — bilan du soir (V10.85.21)
À **22 h 50**, le créneau textuel existant devient le journal de bord de NOX : bilan du défi de 15 h 50 fondé sur les inscriptions réellement enregistrées, remerciements et conclusion humoristique. Si aucun défi n'a été publié, NOX ne prétend pas avoir compté des participations. Aucun message, salon, commande ou rôle supplémentaire.


### V10.85.22 — Célébrations collectives NOX
Les défis quotidiens félicitent en privé les participants qui franchissent les paliers collectifs 3, 5, 10, 15, 20, 30, 50 et 100. Le bilan de 22h50 souligne le plus haut palier atteint, sans publication supplémentaire, classement, XP ni nouvelle commande.

### V10.85.24 — Vérification technique
- Aucun changement de commande utilisateur ; sécurisation de la boucle des publications quotidiennes NOX.
- Ajout de `tests/test_nox_stabilisation_v108524.py` pour les contrôles hors ligne.

### V10.85.25 — Diagnostic de préproduction
- `/noxdiagnostic` (administrateur) : contrôle en lecture seule du salon, des permissions webhook et pièces jointes, des illustrations, des réservations de publication et des identifiants de sondages/défis. Aucun message public ni webhook créé.
- Les réservations en attente ne sont pas réinitialisées automatiquement : vérifier manuellement le message Discord pour éviter les doublons.

- `/noxplanning` (administrateur) : vue privée en lecture seule des 12 créneaux, du salon configuré et des états envoyés / réservés / non enregistrés. Ne publie rien. (V10.85.26)


## Centre NOX — V10.85.27
- `/nox` : tableau de bord principal avec rubriques Univers, Refuge, Animations, Publications, NOX TV et Administration.
- Les anciennes entrées `/noxplanning`, `/noxdiagnostic` et `/noxquotidien` sont remplacées par des boutons dans `/nox` (Administration). Les fonctions restent présentes dans le code.
- NOX TV conserve son sous-panneau et ses commandes avancées. Les autres commandes NOX restent temporairement accessibles jusqu'à leur migration complète, pour ne pas perdre de fonctionnalité.


### V10.85.28 — Centralisation des animations de NOX
- `/nox` → **Animations** : lancer / conclure une aventure et lancer / conclure une mission collective. Les actions sont réservées aux administrateurs et utilisent le salon dans lequel le panneau est ouvert.
- `/nox` → **Refuge** : accès privé aux souvenirs et distinctions.
- Les commandes slash `/noxaventure`, `/noxmission`, `/noxmemoire` et `/noxtitres` sont remplacées par ces boutons. La logique métier et les données sont conservées.
- `/nox` → **Administration** : planning, diagnostic et configuration du quotidien.


### V10.85.29 — Réglages NOX centralisés
Les anciennes commandes `/noxpresence`, `/noxvie`, `/noxevenements`, `/noxsurprise` et `/noxroles` ne sont plus enregistrées comme commandes slash. Leurs fonctions sont accessibles dans `/nox`, via les menus privés. La synchronisation des rôles conserve sa pagination.


### V10.85.30 — Publications depuis `/nox`
- `/nox` → Publications → **Publier une réplique** : catalogue des 20 messages, publication dans le salon actuel (administration).
- `/nox` → Publications → **Faire parler NOX** : formulaire de texte personnalisé, publication dans le salon actuel (administration).
- `/noxpublier` et `/me` ne sont plus enregistrées comme commandes slash. Les méthodes internes sont conservées pour le tableau de bord.
- Les fonctions des autres commandes ne sont pas modifiées dans cette étape.


### V10.85.34 — Livraison finale candidate (remplace les anciennes indications NOX ci-dessus)
- `/nox` : centre de contrôle principal, rubriques Publications, Animations, Refuge, NOX TV, Administration.
- `/nox` → Administration → Planning, Diagnostic, Configurer le quotidien.
- `/nox` → Publications → Publier une réplique, Faire parler NOX.
- `/nox` → Animations → Aventures, Missions, Surprise.
- `/nox` → Refuge → Souvenirs, Distinctions.
- Les commandes `/noxquotidien`, `/noxdiagnostic`, `/noxplanning`, `/noxaventure`, `/noxmission`, `/noxmemoire`, `/noxtitres`, `/noxpresence`, `/noxvie`, `/noxevenements`, `/noxsurprise`, `/noxroles`, `/noxpublier` et `/me` mentionnées dans l'historique **ne sont plus des commandes slash à utiliser**.
- `/dashboard` : tableau de bord staff ; `/centre` : centre membres ; `/aide` et `/aidestaff` : aides.
- Pour NOX TV, privilégier `/nox` → NOX TV ; consulter `/aide` pour les autres commandes encore réellement enregistrées.


V10.85.43 : le bouton « Faire parler NOX » du tableau `/nox` illustre les textes libres selon leur thème (portrait neutre sinon), sans nouvelle commande.

## Audit V10.85.44
Aucune nouvelle commande slash. NOX TV conserve sa réservation de publication quotidienne si l'envoi échoue de manière ambiguë, afin de limiter les doublons. Tests Discord à effectuer lors de la mise en production.


### V10.85.45 — Audit tableaux de bord
Aucune nouvelle commande. `/centre` acquitte les interactions avant les accès SQLite ; correction d’un ancien callback de navigation staff.


## V10.85.46 — Candidate finale
Aucune nouvelle commande. Recette et déploiement : `V10_85_46_RAPPORT_FINAL.md`.


### V10.85.50 — Audit cohérence NOX
Aucune nouvelle commande. Restauration des boutons d’aventure liée au message Discord, validation des votes et robustesse des interventions spontanées.

## V10.85.51 — Fiabilisation du programmateur NOX

Aucune nouvelle commande. Les identifiants des sondages/défis et l'état des publications sont enregistrés dans une transaction unique. En cas d'échec d'envoi incertain, la réservation est conservée pour éviter les doublons. Voir `V10_85_51_RAPPORT.md`.

## NOX Junior V0.1 (fondations)
- `/monnox` : adoption privée (rôle Lien vivant `1567215752656715927` et 10 soins au NOX collectif), sélection de compagnon, soins et renommage unique.
- `/givemonnox membre` : rôle Fondateur `1566561887305339001` uniquement ; autorisation confirmée d'une deuxième adoption (maximum deux).
- Soins Junior : 30 minutes de repos partagé entre les soins ; croissance par temps, complicité et activités.
- Les mini-jeux complets, inventaires, cadeaux, chambres, talents et rencontres sont **prévus mais non encore implémentés** en V0.1.

## NOX Junior V0.2 — Vie quotidienne
- `/monnox` : panneau privé avec les six soins (nourrir, boire, jouer, câlin, laver, repos), actualisation des cinq jauges et humeur contextuelle.
- Bouton **Journal** : dernières actions horodatées du compagnon ; bouton **Actualiser** : recalcul de l'état du compagnon.
- Les jauges diminuent progressivement lors des consultations, avec un plancher de 30/100 et un maximum de 72 h de décroissance comptabilisée par période hors ligne.
- Les six soins partagent le même repos de 30 minutes ; le renommage reste limité à une fois.
- Les jeux avancés, les talents, les cadeaux, les rencontres et les chambres illustrées ne sont pas encore livrés.

## NOX Junior V0.3 — Jeux et présentation
- `/monnox` : bouton **Mini-jeux** (chasse aux étoiles, mémoire cosmique, décision cosmique) et bouton **Talents** (affinités enregistrées). Récompenses plafonnées à une partie par dix minutes et par compagnon.
- `/montrermonnox [compagnon:1|2]` : publie volontairement dans le salon courant une illustration originale du bébé NOX et sa fiche (nom, âge, stade, couleur, humeur, complicité, activités et talent si révélé). Aucun message automatique.
- `/givemonnox membre` : autorisation Fondateur de deuxième adoption, inchangée.

## NOX Junior V0.4
- `/monnox` : panneau privé, six mini-jeux (Chasse aux étoiles, Mémoire cosmique, Décision cosmique, Cristaux mystérieux, Énigmes stellaires, Constellations), explorations dans cinq régions et carnet des découvertes.
- `/montrermonnox` : présentation publique volontaire avec portrait.
- `/givemonnox` : attribution exceptionnelle Fondateur.
- Les six mini-jeux restants (Parcours cosmique, Course des comètes, Mission sauvetage, Duo des étoiles, Chasse au trésor collective, Festival cosmique) sont prévus pour les phases suivantes.

## NOX Junior V0.5
- `/monnox` : neuf mini-jeux, dont Parcours cosmique, Course des comètes et Mission sauvetage.
- `/monnox` → **Journal** : souvenirs automatiques, notes personnelles (titre 80 caractères, texte 1 000 caractères), création, lecture, modification, suppression confirmée et partage public confirmé. Chaque compagnon conserve son journal indépendant.
- `/montrermonnox` : présentation publique volontaire, inchangée.
- `/givemonnox` : attribution exceptionnelle Fondateur, inchangée.
- Jeux sociaux restants : Duo des étoiles, Chasse au trésor collective, Festival cosmique (3 jeux).

## NOX Junior V0.6 — Inventaire, cadeaux et chambres
- `/monnox` → **Sac cosmique** : consulter les objets gagnés en exploration, fabriquer une veilleuse ou un coussin avec les matériaux nécessaires, proposer un cadeau à un autre membre possédant un NOX Junior.
- `/monnox` → **Chambre** : choisir un thème et installer une décoration réellement possédée ; chambre indépendante pour chaque compagnon.
- `/monnox` → **Cadeaux reçus** : accepter ou refuser les propositions en attente (expiration 24 h). Les objets non transférables, notamment les souvenirs, sont protégés.
- Les explorations terminées attribuent désormais un matériau à l'inventaire, en transaction avec la récompense existante.
- Aucune commande slash supplémentaire. `/montrermonnox` reste inchangée.

## NOX Junior V0.7 — Rencontres cosmiques
- `/monnox` → sélectionner son compagnon → **Rencontres** : proposer une rencontre à un autre membre possédant un NOX, consulter les invitations reçues ou envoyées et jouer après consentement.
- Trois mini-jeux sociaux supplémentaires : **Duo des étoiles**, **Chasse au trésor collective** et **Festival cosmique** (12 mini-jeux au total : 9 individuels + 3 coopératifs).
- Les invitations expirent après 24 h ; la participation des deux propriétaires est indispensable avant toute récompense. Récompenses attribuées une seule fois aux deux NOX, sauvegardées dans SQLite.
- Aucune nouvelle commande slash. `/montrermonnox` reste une présentation publique volontaire.

### NOX Junior V0.8 — Visuels
- `/monnox` → bouton **Portrait** : illustration privée selon l'âge, la couleur, l'humeur et la chambre du compagnon.
- `/monnox` → **Chambre** : aperçu illustré de l'ambiance choisie.
- `/montrermonnox [compagnon]` : portrait public volontaire reflétant l'évolution et l'ambiance.
- Aucun nouveau slash-command : toutes les actions restent regroupées dans le panneau personnel.

### NOX Junior V0.9 — rencontres en trois manches
- `/monnox` → **Rencontres** → invitation et acceptation inchangées.
- Les trois jeux coopératifs (Duo des étoiles, Chasse au trésor collective, Festival cosmique) proposent chacun **3 manches**, avec trois décisions par manche.
- Chaque membre joue une fois par manche ; le passage à la suivante exige les deux choix. Reprendre dans `/monnox` → Rencontres après la réponse du partenaire.
- Récompense commune une seule fois, à la fin des trois manches, avec bonus pour les choix complémentaires.
- Aucune commande slash supplémentaire.


### NOX Junior V1.0 — Couleur arc-en-ciel 🌈 et consolidation
- `/monnox` → **Adopter** : 9 couleurs disponibles, dont **🌈 Arc-en-ciel** (`arc_en_ciel`), avec motifs multicolores sur l'œuf et le compagnon à chaque stade.
- `/monnox` → **Portrait** et **Chambre** : illustrations adaptées aux neuf couleurs, aux âges et aux humeurs.
- `/montrermonnox [compagnon]` : présentation publique facultative avec portrait multicolore.
- `/givemonnox membre` : **Fondateur uniquement**, autorisation d'adopter un deuxième compagnon.
- `/aide` et `/aidestaff` : catalogue dynamique classant les commandes NOX Junior, avec restriction staff correcte pour `/givemonnox`.
- Aucun changement de couleur automatique pour les compagnons existants. Aucune nouvelle commande slash.
- Dépendance Pillow ajoutée à `requirements.txt` pour éviter un échec d'import au déploiement.

### NOX Junior V1.6 — mini-jeux
Depuis `/monnox` → **Mini-jeux**, 12 activités sont disponibles, dont **Cache-cache cosmique**, **Cuisine des étoiles** et **Danse des constellations**. Les parties sont rejouables ; seules les cinq premières parties terminées par jour rapportent 2 Poussières d'étoiles chacune.


## Tickets — prise en charge et archivage

- Le bouton **Prendre en charge** attribue un ticket ouvert à un seul membre du staff.
- Le responsable du ticket, son auteur ou un administrateur peuvent le fermer selon les permissions applicables.
- À la fermeture, le bot lit l’historique complet et transmet une transcription horodatée en fichiers texte au salon configuré par `TICKET_LOG_CHANNEL_ID` (logs-tickets). Les liens vers les pièces jointes sont inclus, mais pas les fichiers eux-mêmes.
- Si la lecture de l’historique ou l’envoi de l’archive échoue, le ticket reste ouvert. Une clôture simultanée est bloquée pour éviter des archives en double au sein du même processus.
- Le salon du ticket fermé est conservé pour consultation. Les messages supprimés avant l’archivage ne peuvent pas être restaurés.


## Administration de la structure et recrutement Staff

- `/structure` (ancienne commande retirée) : aperçu des renommages, application après confirmation ou suppression distinctement confirmée des trois salons abandonnés. Les permissions existantes sont conservées ; la suppression des salons efface leur historique Discord.
- `/reglement_staff` (ancienne commande retirée) : publie ou actualise le règlement Staff. Les candidats avec le rôle **Staff en attente** acceptent par bouton ; le Fondateur reçoit la demande dans **logs-fondateur**, choisit Animateur, Médiateur, Modérateur ou Administrateur, ou refuse. Après approbation, les rôles **Équipe STAFF** et de fonction sont attribués, et **Staff en attente** est retiré.
- Les fonctionnalités **Regard du Jour** et **météo des émotions** ont été retirées des panneaux et commandes ; leurs anciennes données ne sont pas supprimées automatiquement.
- Le salon général est renommé **🌌・𝓛𝓐 𝓟𝓛𝓐𝓒𝓔・💬** par `/structure`, avec une description explicite.


## Profil et anniversaires — nouvelle interface

- `/installer_roles` (administration) : crée les rôles de profil manquants et sauvegarde leurs identifiants dans `data/role_catalog.json`. À lancer **une seule fois** après la mise à jour ; relançable sans doublons.
- `/publier_roles` (gestion du serveur) : remplace les anciens panneaux enregistrés par un panneau unique de boutons. Les sélections sont privées, et les choix peuvent être retirés.
- `/prochains_anniversaires` : affiche les dix prochains anniversaires enregistrés, sans divulguer les années de naissance.
- Les anciennes commandes `/structure` et `/reglement_staff` ont été retirées. Les panneaux Staff déjà publiés restent utilisables.
- Les anciens rôles de zones cardinales et de tranches d'âge ne sont **pas supprimés automatiquement** : vérifier les attributions existantes avant un nettoyage manuel.


## Escape Game — Les Fractures du Cosmos (tests locaux validés, Discord non testé)
- `/escape installer` : crée ou retrouve la catégorie et les cinq salons et publie les panneaux permanents (administrateur).
- `/escape jouer mode:Solo` : ouvre la salle actuelle de la partie personnelle, ou crée une sauvegarde au premier lancement.
- `/escape jouer mode:Collectif` : ouvre la salle de l’équipe à laquelle appartient le membre.
- `/escape inviter` : invite un membre dans une équipe de 2 à 6 (capitaine).
- `/escape rejoindre` : accepte une invitation à une équipe.
- `/escape refuser` : refuse une invitation à une équipe.
- Panneau permanent : jouer en solo, créer une équipe, consulter sa progression et les aventures.
- Dans une salle : examiner les épreuves, répondre, demander un indice, explorer le décor, consulter l’inventaire, assembler deux objets et actualiser la salle.
- Les deux autres aventures sont annoncées « À venir prochainement ».
- **État de validation :** le catalogue des 13 salles et les fonctions principales sont présents dans le projet de travail ; les tests Python locaux ne remplacent pas un essai sur Discord. Les audits automatisés des 13 images et des repères visuels réussissent ; la vérification Discord réelle et l’intégration finale restent à effectuer avant diffusion.
- Les réponses et secrets ne doivent jamais figurer dans les messages publics ou la documentation des membres.
