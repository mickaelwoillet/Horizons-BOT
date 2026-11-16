# Étape 16 — Récompenses

- Attribution du rôle en solo et en équipe : tests unitaires réussis (3/3).
- Création du rôle une seule fois et attribution idempotente vérifiées avec simulation Discord.
- Échec de création du rôle non bloquant ; participants signalés pour vérification staff.
- Erreur de lecture SQLite des participants journalisée sans faire échouer la victoire.
- Aucun test réel sur un serveur Discord effectué.
- Les logs événements et le comportement des interfaces après inactivité nécessitent encore des tests.
