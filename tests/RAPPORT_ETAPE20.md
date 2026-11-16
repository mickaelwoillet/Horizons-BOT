# HORIZONS Escape Game V1.1 — Étape 20

Test ajouté : `python tests/test_escape_v11_restart.py`.

Résultats sur base SQLite temporaire :
- Session solo conservée après recréation du moteur : salle, objets et énigmes résolues.
- Session équipe conservée après recréation du moteur : salle, objets et énigmes résolues.
- `start()` n'efface pas une partie existante.
- Isolation des sauvegardes par serveur et mode.
- Tests simulés du rôle et des logs relancés avec succès.

Limites : ne simule ni le redémarrage du processus Discord réel, ni l'expiration des Views, ni les permissions sur le serveur. Les données de test sont artificielles et stockées hors des sauvegardes des membres.
