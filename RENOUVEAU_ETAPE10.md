# Renouveau HORIZONS — Étape 10 (travail intermédiaire)

- Catalogue dynamique /aide et /aidestaff : retrait des catégories Missions et Saisons, ajout de /renouveau au groupe de gestion et classement des commandes d'administration.
- Sécurisation de /renouveau supprimer_salons : refus de supprimer un salon dont le nom ne correspond plus à celui de l'export. Toujours confirmer manuellement ; aucun appel Discord effectué.
- Audit de références de modules et banques : voir AUDIT_RENOUVEAU_DEPENDANCES.json. Aucune suppression physique sans validation des dépendances.

ATTENTION : le catalogue des commandes est dynamique : si un module chargé expose encore une ancienne commande, elle peut apparaître dans les commandes restantes. Ce point reste à corriger avant livraison finale.
Tests : compilation Python et ZIP uniquement, pas de test Discord.
