# 🌅 Salon « aujourd'hui sur HORIZONS »

## Création automatique
Au premier démarrage du bot après mise à jour, l'extension `cogs.today_hub`
recherche le salon `🌅・aujourd-hui-sur-horizons` puis le crée s'il n'existe pas.
Il est placé dans la catégorie « Expériences » (`EXPERIENCES_CATEGORY_ID`)
si elle existe, sinon à la racine du serveur. Le bot doit disposer de
la permission **Gérer les salons**.

La création ne peut pas se produire tant que le ZIP n'est pas installé et
le bot redémarré. Aucune modification n'a été effectuée directement sur Discord.

## Permissions à la création
- `@everyone` : voir le salon refusé.
- Rôle nouveau membre : voir le salon refusé.
- Rôle membre validé : voir l'historique et utiliser les composants,
  mais pas envoyer de messages ou réactions.
- Rôles staff, administration, modération et animation : voir le salon
  et utiliser le panneau ; pas de messages ordinaires.
- Bot : voir, envoyer, intégrer des embeds et gérer les messages.
- Les administrateurs Discord conservent leurs permissions natives.

Sur un salon déjà existant, le bot **ne modifie pas les permissions** :
ceci évite d'écraser des choix manuels. Il réutilise le salon et son panneau.

## Panneau permanent
Un menu interactif propose : Discuter, Jouer, Explorer, Rencontrer,
Participer, Faire une pause. Le bot répond en privé avec un bouton-lien
vers le salon concerné. Aucun nouveau slash command n'est créé.

Le panneau est recherché via l'ID stocké dans `bot_settings` ou via sa
signature `HORIZONS-TODAY-HUB:v1`. Il est mis à jour sur place à chaque
vérification (toutes les six heures), sans message supplémentaire.

Les liens vers l'Arcade et les Trésors sont résolus par les noms de salon
existants. Les autres liens utilisent les identifiants configurés.
Si une destination manque ou n'est pas accessible au membre, le bot
l'indique en privé sans créer de salon imprévu.

## Vérifications à faire lors de la mise en ligne
1. Confirmer la présence du salon dans la bonne catégorie.
2. Vérifier l'accès avec un membre validé et un nouveau membre.
3. Vérifier les six choix du menu et leurs salons cibles.
4. Redémarrer le bot : vérifier qu'il n'a pas créé de doublon.
5. Confirmer que le bot possède `Gérer les salons`, `Voir le salon`,
   `Envoyer des messages`, `Intégrer des liens`, `Lire l'historique`.
