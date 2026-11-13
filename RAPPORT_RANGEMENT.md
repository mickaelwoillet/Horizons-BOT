# HORIZONS — rangement prudent du projet

Archive créée à partir de Bot Horizons(4).zip. Aucun fichier .env, aucune base SQLite et aucun dossier .git n'étaient présents dans l'archive reçue.

## Retirés (5 fichiers)
- `patch.py` : Ancien script de modification avec chemin de développement absolu.
- `continue_patch.py` : Ancien script de modification avec chemin de développement absolu.
- `data/docs/HISTORIQUE_DES_VERSIONS.md` : Copie strictement identique de docs/HISTORIQUE_DES_VERSIONS.md.
- `docs/NOX_TV_CONTROLE_VISUEL_GIFS.png` : Illustration documentaire en double du WebP déjà conservé.
- `data/nox_tv/nox_refuge_lanternes.webp` : Image strictement identique à nox_refuge_bain.webp et sans référence textuelle.

## Conservés volontairement
- Les modules `cogs/`, fichiers JSON, illustrations et catalogues.
- Le dossier `tests/` : utile pour contrôler les prochaines évolutions, pas des journaux.
- `preflight_v1078.py` : vérification technique réutilisable.
- Les images aux noms différents même lorsque leur contenu est identique si elles peuvent être référencées par le code ou les catalogues.
- Les fichiers JSON vides, qui peuvent être des états initiaux requis.

## Fichiers absents de l'archive fournie
`install_windows.bat`, `start__windows.bat`, `COMMANDES.md`, `README.md` et `.git/` n'ont pas été fournis et ne sont pas recréés artificiellement. Réintègre les fichiers de documentation et de lancement depuis ta copie si tu les utilises.

## Attention à Git
`.git/` n'est pas un dossier de logs : il contient l'historique, les branches et la configuration du dépôt local. Ne le supprime pas de ton dépôt de travail. Il est normal de l'exclure d'un ZIP destiné au partage.

## Déploiement
Sauvegarde ton projet, conserve les bases SQLite et le `.env` de l'hébergeur, puis fusionne les fichiers. Une extraction par-dessus un dossier existant ne supprime pas automatiquement les 5 fichiers retirés de cette archive.
