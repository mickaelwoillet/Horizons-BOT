# HORIZONS — Continuité technique V6

## Ce qui est ajouté
Extension `cogs.continuity` chargée par `bot.py`, sans nouvelle commande
slash, sans nouveau salon ni nouvelle catégorie.

### Sauvegardes
- Sauvegarde SQLite cohérente (API `sqlite3.backup`, compatible WAL).
- Au premier démarrage puis environ toutes les 24 h tant que le bot tourne.
- Conservation glissante des sauvegardes locales pendant 14 jours.
- Vérification SQLite de chaque sauvegarde avant conservation.
- Emplacement : `data/backups/horizons-AAAAmmjj-HHMMSS-ffffff.sqlite3`.
- Permissions du fichier limitées à l'utilisateur du processus si le système le permet.

### Surveillance
- Vérification de l'accès et de l'intégrité rapide de SQLite chaque heure.
- Contrôle du chargement des extensions importantes (accueil du jour,
  anniversaires, Trésors célestes, dashboard staff).
- En cas d'anomalie : journalisation et alerte dans le salon de logs
  administrateur déjà configuré (`ADMIN_BOT_LOG_CHANNEL_ID`).
- Pas de message de routine ; répétition des alertes limitée à une
  notification par type toutes les 12 heures pendant que le bot tourne.
- Aucune mention générale, aucun ping automatique du fondateur.

## Limites et précautions
- Ces sauvegardes sont sur **la même machine** que le bot. Une panne de
  disque, suppression du serveur ou attaque peut les détruire avec la base.
  Prévoir une sauvegarde hors machine, chiffrée, avec rétention adaptée.
- Le bot ne peut pas détecter ni signaler lui-même sa propre extinction :
  un service de supervision **externe** et un redémarrage automatique
  (systemd / Docker restart policy / hébergeur) restent nécessaires.
- Les alertes ne garantissent pas qu'un membre du staff les lira.
- Les sauvegardes incluent les données de membres et de modération :
  limiter strictement l'accès et définir une politique de conservation.
- Les tests réalisés sont des tests de syntaxe et de la sauvegarde SQLite,
  pas des essais connectés à Discord.

## Vérifications à l'installation
1. Préserver le dossier `data/` existant avant toute mise à jour.
2. Vérifier que le processus peut écrire dans `data/backups/`.
3. Vérifier qu'une sauvegarde est créée au démarrage.
4. Contrôler les journaux et le salon de logs administrateur.
5. Mettre en place une copie hors machine et tester la restauration sur
   une copie de la base (jamais sur la production sans arrêt du bot).
6. Mettre en place un redémarrage automatique au niveau de l'hébergement.

## Suite recommandée
- Ajouter une supervision externe (alerte lorsque le processus est arrêté).
- Tester une restauration complète.
- Définir un relais staff pour les alertes techniques et humaines.
- Auditer les publications après coupure afin d'éviter les doublons.
