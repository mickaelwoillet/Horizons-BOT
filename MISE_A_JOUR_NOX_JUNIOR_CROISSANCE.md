# HORIZONS — Notifications de croissance NOX Junior

- À chaque changement de stade (œuf → nouveau-né → bébé → adolescent → adulte), NOX envoie un message amusant et explicatif au propriétaire.
- Envoi par message privé en priorité ; si les MP sont fermés, tentative de mention dans le salon du cadeau NOX Junior.
- Le message explique comment choisir ou décorer la chambre depuis `/monnox` et rappelle le cadeau du premier choix.
- Vérification des changements toutes les trois minutes, sans nouvelle commande Discord.
- État mémorisé dans la table SQLite `junior_growth_notifications` de la base existante `data/nox_junior.sqlite3` : pas de répétition au redémarrage.
- Les compagnons existants sont initialisés à leur stade courant pour éviter des notifications rétroactives.
- La croissance reste soumise aux critères déjà prévus (âge, complicité, activités).

## Installation
Arrêter le bot, sauvegarder les données, remplacer les fichiers du code et les ressources de l'archive. Ne pas écraser `.env` ni les bases SQLite. Redémarrer normalement. Tester une évolution de stade en conditions réelles.

## Note
Le ZIP contient le code et les ressources du projet, sans secrets ni bases de données. L'envoi Discord n'a pas été testé sur un serveur réel.
