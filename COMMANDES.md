# Commandes HORIZONS

Les commandes slash sont disponibles depuis Discord. Les commandes d'équipe nécessitent le rôle configuré ou les permissions Discord indiquées.

## Membres
- `/ping` — vérifier la latence du bot.
- `/aide` — afficher le centre d'aide interactif (réponse privée).
- `/profil [membre]` — afficher le profil public d'un membre.
- `/serveur` — afficher les informations de HORIZONS.
- `/presentation` — rappeler le salon de présentation.
- `/proposer idee` — transmettre une suggestion à l'équipe.
- `/ticket_ouvrir sujet details` — ouvrir un espace privé avec l'équipe.
- `/ticket_fermer` — fermer son ticket dans le salon concerné.
- Dans le salon **Demande de ticket**, cliquer sur **Créer un ticket** ouvre également un formulaire privé.
- `/signaler motif [salon] [message_id]` — transmettre un signalement confidentiel.
- `/anniversaire_definir jour mois` — enregistrer son anniversaire sans année de naissance.
- `/anniversaire_supprimer` — effacer son anniversaire.
- `/mon_parcours` — consulter son rang honorifique.

## Communauté et détente
- `/question_du_jour` — proposer une question de discussion.
- `/compliment [membre]` — partager un message positif.
- `/traduire texte langue` — traduction si un service LibreTranslate est configuré.
- `/blague [categorie]` — afficher une blague, puis utiliser « Une autre ! ».
- `/devinette` — jouer et révéler la réponse avec les boutons.

## Quiz culturel
- `/quiz_lancer [manches]` — lancer un quiz de 1 à 10 manches dans le salon configuré (équipe uniquement, 12 joueurs maximum).
- Les participants cliquent sur **Participer**, puis **Proposer une réponse**.
- Une seule tentative est autorisée par participant et par manche.
- Une bonne réponse rapporte un point ; le classement cumulé est publié à la fin.
- Chaque manche dure au maximum 10 minutes.
- `/quiz_arreter` — arrêter le quiz et publier le classement (équipe uniquement).

## Événements et concours
- `/evenement_creer titre date_heure description salon [lieu]` — publier un événement.
- `/evenements` — consulter les prochains événements.
- `/evenement_fermer numero` — fermer les inscriptions (créateur ou équipe).
- `/concours_creer prix duree_heures [gagnants] [salon]` — créer un concours.
- `/concours_annuler numero` — annuler un concours (équipe uniquement).

## Équipe et modération
- `/annonce salon titre message [image]` — publier une annonce officielle.
- `/alerte_equipe message` — alerte interne urgente.
- `/message_anonyme message` — publication anonyme dans le salon configuré.
- `/avertir membre raison` — ajouter un avertissement.
- `/avertissements membre` — consulter les avertissements actifs.
- `/retirer_avertissement numero` — clôturer un avertissement.
- `/timeout membre minutes [raison]` — mise en timeout.
- `/untimeout membre [raison]` — retirer un timeout.
- `/expulser membre [raison]` — expulser.
- `/bannir membre [raison]` — bannir.
- `/debannir utilisateur_id [raison]` — débannir.
- `/purger nombre` — supprimer jusqu'à 100 messages dans le salon actuel.
- `/note_membre membre note` — ajouter une note interne.
- `/actualiser_rangs` — recalculer les rangs (permission Gérer les rôles requise).

## Publications automatiques (heure de Paris)
- 09 h 00 : souhaits d'anniversaire, si des membres ont choisi d'enregistrer leur date.
- 10 h 00 : question du jour.
- 12 h 00 : blague du jour.
- 12 h 15 : devinette du jour.

## Configuration requise
- Les salons de vocaux temporaires, le panneau de tickets et les messages anonymes sont configurés dans `.env`.
- La traduction reste désactivée tant que `TRANSLATE_API_URL` n'est pas renseignée.
- Les sept identifiants de rôles honorifiques doivent être ajoutés dans `RANK_ROLE_IDS`.
- Le fichier `.env` doit rester local et ne doit jamais être partagé.


## Expériences HORIZONS

### Passeport
- `/mon_passeport` : consulter les trois missions de la semaine.
- `/valider_mission` : valider une mission accomplie (validation déclarative, basée sur la confiance).

### Rencontres et activités
- `/chercher` : publier une annonce dans `#cherche-quelquun`. Les membres intéressés utilisent le bouton de l'annonce ; l'auteur reçoit un message privé.
- Le salon de recherche peut être un salon textuel ou un Forum.
- Les annonces expirent après la durée choisie (1 à 24 heures).

### Défis collectifs
- `/defi_collectif` : consulter le défi en cours.
- `/rejoindre_defi` : participer une seule fois au défi en cours.
- `/creer_defi` : créer un défi (permission Gérer le serveur), avec un objectif de membres et une durée de 1 à 30 jours.
- Le défi est automatiquement marqué comme réussi lorsque l'objectif de participants est atteint.

## Parcours des horizons
- `/parcours` — consulter et faire progresser son parcours personnel avec les boutons interactifs.
- `/parcours_badges` — consulter les badges de thèmes débloqués.
