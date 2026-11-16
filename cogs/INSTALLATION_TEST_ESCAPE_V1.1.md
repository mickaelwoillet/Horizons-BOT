# HORIZONS — Escape Game V1.1 — Installation et test Discord

## Avant remplacement
1. Arrêter le bot.
2. Copier le dossier actuel en sauvegarde (notamment `.env`, `data/`, toutes les bases SQLite et les ressources personnalisées).
3. Ne jamais écraser les fichiers de configuration ou les sauvegardes par des versions vierges.
4. Décompresser l'archive dans un dossier séparé, comparer et mettre à jour le code/ressources en préservant les données locales.
5. Redémarrer le bot, vérifier les erreurs du terminal et la synchronisation des commandes.

## Préparer les salons
- Lancer `/escape installer` avec les droits administrateur.
- Vérifier la catégorie 🔐 ESCAPE GAME, le portail 🌌・fractures-du-cosmos et le salon 📨・invitations.
- Vérifier que le bot peut voir les salons, envoyer des messages et intégrer des liens.
- Vérifier le prologue et les boutons sans doublons.

## Parcours de validation : une salle complète
1. Sur un compte de test, ouvrir le portail et démarrer en solo depuis la salle 1.
2. Vérifier le descriptif, les indices, les explorations, l'inventaire et les énigmes.
3. Résoudre le verrou final de la salle et vérifier l'ouverture de la salle 2.
4. Fermer le panneau puis relancer `/escape jouer` : vérifier que la progression est conservée.
5. Redémarrer le bot et vérifier à nouveau la progression et les boutons.
6. Facultatif : tester la création d'équipe et une invitation publique avec un deuxième compte.
7. Vérifier les logs d'événement dans le salon configuré.

## Limites des tests automatiques
Les tests exécutés ici sont hors Discord. Ils vérifient le moteur, les transitions, la persistance, les récompenses et certains logs. Ils ne garantissent pas les permissions réelles, les interactions de boutons, le réseau Discord ou les autres modules du bot.

## En cas de problème
Conserver l'ancienne archive et les sauvegardes. Revenir à l'ancienne version du code sans remplacer la base de données par une version vierge. Fournir le traceback du terminal et le nom du bouton ou de la commande en échec.
