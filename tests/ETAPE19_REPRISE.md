# Escape Game V1.1 — Étape 19

Modification : le bouton persistant « Ma progression » consulte désormais le moteur et affiche l’identifiant de la salle sauvegardée en solo et en équipe. Il rappelle la commande de reprise.

Limite Discord : les vues éphémères expirées ne peuvent pas être réactivées ; `/escape jouer` crée un nouveau panneau à partir de SQLite. La persistance du portail est déjà enregistrée via `bot.add_view(Portal())`.

Contrôles : compilation du fichier modifié et intégrité ZIP. Les tests en conditions réelles restent à faire.
