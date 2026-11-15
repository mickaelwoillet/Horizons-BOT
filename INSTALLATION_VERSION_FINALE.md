# HORIZONS — Livraison consolidée (15 novembre 2026)

## Installation
1. Sauvegarder intégralement l'installation actuelle, particulièrement `.env` et les bases SQLite de `data/`.
2. Décompresser cette archive dans un dossier séparé, puis comparer et conserver les données de production existantes. Ne jamais écraser les bases SQLite actives par des bases vierges.
3. Copier `.env.example` vers `.env` uniquement si aucun `.env` n'existe, puis configurer le jeton Discord et vérifier les IDs et permissions.
4. Installer les dépendances : `python -m pip install -r requirements.txt`.
5. Vérifier : `python preflight_v1078.py` (option : `--structure-export <export.json>`).
6. Démarrer `python bot.py`, contrôler les logs de chargement des extensions et la synchronisation des commandes.
7. Tester sur Discord : `/structure` en aperçu avant application, `/reglement_staff`, une candidature, un ticket de test et son archivage dans logs-tickets, NOX et NOX TV.

## Avertissements
- Contrôles hors ligne réussis ; **aucun test de connexion réelle à Discord ni de permissions n'a pu être effectué dans l'environnement de préparation**.
- `/structure` possède une action de nettoyage destructrice : les salons supprimés et leurs messages ne sont pas récupérables. Faire une sauvegarde/export et vérifier avant confirmation.
- `SUCCESS_CHANNEL_ID` est aligné sur le salon existant des distinctions NOX (`1569434256311193721`) ; les annonces de succès ordinaires pourront aussi y apparaître. Changer la destination dans `.env` si un salon spécifique est souhaité.
- NOX Junior n'a pas fait l'objet de modifications intentionnelles.
