# HORIZONS — Les Fractures du Cosmos V1.1 — Candidate aux tests Discord

## État de validation
Tests locaux exécutés : parcours normal (82 énigmes, salle 12), parcours secret (87 énigmes, salle 13), persistance SQLite solo/équipe, attribution simulée du rôle, logs simulés, audit catalogue et compilation des modules Escape Game. Les interactions réelles Discord et les permissions serveur ne sont PAS encore validées.

## Avant lancement
1. Faire une copie de sauvegarde du bot actuel, de sa base SQLite et de son fichier .env. L'archive de test ne contient pas de .env réel.
2. Vérifier que le jeton Discord et les identifiants des salons dans votre configuration locale sont corrects.
3. Vérifier les permissions du bot : envoyer des messages, intégrer des liens, joindre des fichiers, gérer les rôles. Le rôle du bot doit être au-dessus du rôle honorifique à créer.
4. Effectuer d'abord les essais sur une copie de développement ou en dehors des heures d'activité.

## Checklist sur Discord
- [ ] `/escape jouer` démarre une nouvelle partie solo et affiche la salle 1.
- [ ] Résoudre une énigme, ouvrir l'inventaire et combiner deux objets autorisés.
- [ ] Cliquer sur « Rouvrir la salle » et vérifier l'actualisation de la progression.
- [ ] Laisser une interface inactive plus de 15 minutes : vérifier que `/escape jouer` redonne un panneau fonctionnel sans perte de données. Les anciens boutons ne sont PAS persistants.
- [ ] Redémarrer le bot pendant une partie, puis reprendre avec `/escape jouer`.
- [ ] Vérifier la progression et les objets d'une partie collective après redémarrage.
- [ ] Vérifier dans « Logs événements » : début de partie, changement de salle, victoire.
- [ ] Terminer la voie normale : félicitations, image de victoire, rôle « 🌟 Sauveur du Cosmos ».
- [ ] Terminer la voie secrète avec les dix souvenirs : conclusion distincte et rôle.
- [ ] Vérifier qu'une nouvelle victoire n'attribue pas deux fois le rôle.
- [ ] Vérifier qu'une erreur de permission du rôle ne bloque pas l'enregistrement de la victoire.
- [ ] Vérifier que NOX, NOX Junior et les autres panneaux HORIZONS fonctionnent toujours.

## Retour de bugs
Pour chaque problème, relever la commande/le bouton, le pseudo de test, la salle, l'heure, le message Discord affiché et l'extrait de console correspondant. Ne jamais partager le jeton du bot.
