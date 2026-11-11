# HORIZONS — correctifs pour le bot actuellement installé

Cette archive est construite exclusivement à partir du ZIP de production fourni par l’utilisateur. **NOX Junior n’a pas été ajouté.**

## Corrections
- Ajout de trois réactions persistantes aux six publications illustrées quotidiennes NOX (dont grille-pain et ascenseur). Les votes sont enregistrés en SQLite et modifiables.
- Conservation des sondages, défis et votes du module NOX TV autonome.
- Enregistrement de l’identifiant Discord de chaque publication quotidienne dans la table existante (migration additive).
- Rotation du journal `horizons.log` : 2 Mio par fichier, deux archives (environ 6 Mio).
- Ne charge plus les catalogues des publications quotidiennes si aucun serveur n’a activé ce programme.

## À vérifier sur Discord
- Démarrage et chargement de `cogs.nox_daily_12` sans erreur.
- Présence des trois boutons sous la prochaine publication illustrée et fonctionnement après redémarrage.
- Votes enregistrés une seule fois par membre et modifiables.
- Permissions du webhook NOX, réception des publications et absence de doublons.
- Consommation RAM/CPU réelle sur l’hébergeur.

Les publications déjà envoyées ne sont pas modifiées rétroactivement. La base de données existante doit être sauvegardée avant installation.
