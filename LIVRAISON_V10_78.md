# HORIZONS V10.78 — Préparation de mise en production

## État des validations

- Audit statique du projet et vérification des fichiers Python/JSON : exécutés avec succès.
- Vérification SQLite hors ligne : effectuée sur la base incluse, sans écriture.
- Tests unitaires complets : non exécutés dans l'environnement de préparation (dépendance discord.py absente).
- Tests en ligne sur Discord : **non exécutés**. Les permissions et boutons ne sont pas certifiés.
- Nombre de commandes déclarées : **81** (contrôle statique, pas preuve de synchronisation Discord).

## Mise à jour sûre (serveur arrêté)

1. Arrêter toutes les instances de NOX et NOX TV et vérifier qu'aucune autre instance n'utilise la même base.
2. Sauvegarder le dossier `data/`, le fichier `.env` et toute configuration locale hors de l'archive. Conserver la sauvegarde hors du dossier du bot.
3. Décompresser la V10.78 dans **un nouveau dossier**. Ne pas remplacer le dossier en production directement.
4. Copier les paramètres locaux du serveur (notamment `.env`) vers ce nouveau dossier, sans les publier ni les transmettre.
5. **Ne pas écraser** la base `data/horizons.sqlite3` existante. Conserver les données persistantes du serveur et fusionner avec précaution les nouveaux fichiers de ressources JSON et les médias ; éviter de remplacer les historiques ou les configurations modifiées en production.
6. Installer les dépendances dans un environnement virtuel : `python -m pip install -r requirements.txt`.
7. Exécuter `python preflight_v1078.py`, puis `python tests/check_project.py` et `python -m pytest -q`.
8. Sur un serveur Discord de test, vérifier `/centre`, `/dashboard`, Regardboard, Event, Capsules, NOX et NOX TV ; vérifier les droits d'un membre, d'un modérateur et d'un administrateur.
9. Vérifier le chargement des extensions, les publications programmées et l'absence de doublons après un redémarrage contrôlé.
10. Déployer seulement après validation, en conservant l'ancienne version et la sauvegarde pour un retour arrière.

## Précautions

- La synchronisation des commandes slash dépend du démarrage du bot connecté au serveur cible. Les anciennes commandes peuvent subsister temporairement selon le mode de synchronisation ; vérifier la liste réelle dans Discord.
- Le prévol ne se connecte pas à Discord, ne modifie pas les données et ne valide pas les interactions en ligne.
- Ne jamais communiquer le jeton Discord ni inclure un `.env` réel dans un ZIP.
- En cas de problème, arrêter le bot et restaurer **ensemble** la version précédente et les données sauvegardées.
