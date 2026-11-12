# Correction NOX Junior — illustrations

Le thème de chambre par défaut `cosmos` utilisait auparavant le dessin de secours et ignorait les illustrations WebP dans `data/nox_junior/characters/`.

Le moteur affiche désormais les illustrations du stade nouveau-né et bébé pour les neuf couleurs. Les nouveau-nés transparents sont composés sur un fond cosmique ; les illustrations bébé possédant déjà un décor sont affichées en plein format.

Vérifications hors Discord : 81 combinaisons de couleur/stade/émotion rendues sans erreur, et analyse syntaxique de tous les modules Python.

**Mise à jour :** arrêter le bot, sauvegarder les bases SQLite et `.env`, copier les fichiers de l'archive dans le projet et redémarrer. L'archive ne contient ni jeton `.env` ni base SQLite. Ne pas écraser les données persistantes de l'hébergeur.

**Limites :** les visuels adolescent et adulte ne font pas partie des collections complètes de personnages présentes dans l'archive fournie ; ils continuent d'utiliser le rendu de secours. Les œufs rose et turquoise sont également absents du dossier `eggs` fourni.
