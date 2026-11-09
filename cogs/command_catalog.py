"""Catalogue partagé des commandes réellement enregistrées dans l'arbre slash."""
from __future__ import annotations

import discord
from discord import app_commands
from .embed_theme import horizons_embed

# Les commandes ci-dessous ont un contrôle d'accès staff dans leur implémentation.
# Les autorisations exactes restent vérifiées par la commande elle-même.
STAFF_ONLY = {
    "aidestaff", "annonce", "export_structure", "idee_statut", "actualiser_rangs",
    "evenement_creer", "creer_defi", "giveaway creer", "giveaway annuler", "giveaway reroll",
    "quiz_lancer", "quiz_arreter", "publier_roles", "publier_guides_cercles",
    "accueil_bilan", "saison_lancer", "saison_clore", "givegratte",
    "avertir", "avertissements", "retirer_avertissement", "timeout", "untimeout",
    "expulser", "bannir", "debannir", "purger", "note_membre", "dashboard",
    "horizons_dashboard", "tache_creer", "taches", "tache_statut", "service",
    "alerte_equipe",
}
MIXED_ACCESS = {
    "evenement_fermer": "Membres (créateur de l'événement) et équipe",
    "ticket_fermer": "Membres (dans leur ticket) et équipe habilitée",
}
STAFF_PERMISSIONS = {
    "export_structure": "Permission Administrateur Discord.",
    "annonce": "Rôle staff autorisé ou permission de gestion prévue par le serveur.",
    "idee_statut": "Rôle staff ou administrateur.",
    "actualiser_rangs": "Permission Gérer les rôles.",
    "evenement_creer": "Rôle staff ou administrateur.",
    "creer_defi": "Permission Gérer le serveur.",
    "giveaway creer": "Administrateur ou rôle staff.",
    "giveaway annuler": "Administrateur ou rôle staff.",
    "giveaway reroll": "Administrateur ou rôle staff.",
    "quiz_lancer": "Administrateur ou rôle staff.",
    "quiz_arreter": "Administrateur ou rôle staff.",
    "publier_roles": "Administrateur, Gérer le serveur ou rôle staff.",
    "dashboard": "Staff habilité ; certaines rubriques exigent une prise de service.",
    "horizons_dashboard": "Staff habilité ; statistiques collectives uniquement.",
    "tache_creer": "Staff habilité en service (création selon niveau d'accès).",
    "taches": "Fondateur, administrateur ou modérateur en service.",
    "tache_statut": "Staff en service ; les membres du staff modifient leurs tâches attribuées.",
    "service": "Staff habilité ; permet de prendre ou terminer son service.",
    "alerte_equipe": "Commande d'alerte interne, accès staff.",
    "aidestaff": "Réservée aux membres de l'équipe autorisés.",
    "givegratte": "Permission Administrateur Discord.",
    "publier_guides_cercles": "Permission Administrateur Discord.",
    "accueil_bilan": "Permission Gérer le serveur.",
    "saison_lancer": "Équipe HORIZONS habilitée.",
    "saison_clore": "Équipe HORIZONS habilitée.",
}
CATEGORIES = (
    ("🙌 Accueil et découverte", {"premiers_pas"}),
    ("⚙️ Informations et profils", {"centre", "ping", "aide", "aidestaff", "profil", "serveur", "presentation"}),
    ("💬 Communauté et entraide", {"question_du_jour", "compliment", "idee", "mes_idees", "idee_statut", "remercier", "proposer"}),
    ("🧭 Missions et expériences", {"mon_passeport", "valider_mission", "chercher", "defi_collectif", "rejoindre_defi", "creer_defi", "parcours", "parcours_badges", "mon_parcours", "actualiser_rangs"}),
    ("🎉 Événements et jeux", {"evenement_creer", "evenements", "evenement_fermer", "creer", "annuler", "reroll", "quiz_lancer", "quiz_arreter", "blague", "devinette"}),
    ("🎮 Arcade et progression", {"jeux", "xpjeux"}),
    ("🌌 Trésors et constellations", {"gratter", "givegratte", "echanger_fragments", "echanger_poussiere", "collection_etoiles", "constellations", "inventaire_celeste", "souvenirs_celestes", "etoile"}),
    ("🌠 Saisons", {"saison", "rejoindre_saison", "missions_saison", "valider_etape_saison", "mes_recompenses_saison", "saison_lancer", "saison_clore"}),
    ("🎂 Anniversaires", {"anniversaire_supprimer"}),
    ("🌿 Bien-être et affinités", {"humeur", "ma_meteo", "mes_succes", "affinites activer", "affinites desactiver", "affinites trouver"}),
    ("🎫 Assistance et sécurité", {"ticket_ouvrir", "ticket_fermer", "signaler", "message_anonyme", "traduire"}),
    ("🛡️ Modération et gestion", {"avertir", "avertissements", "retirer_avertissement", "timeout", "untimeout", "expulser", "bannir", "debannir", "purger", "note_membre", "annonce", "alerte_equipe", "dashboard", "horizons_dashboard", "tache_creer", "taches", "tache_statut", "service", "publier_roles", "aidestaff", "export_structure", "publier_guides_cercles", "accueil_bilan"}),
)

def _category(name: str) -> str:
    if name.startswith("giveaway "):
        return "🎉 Événements et jeux"
    if name.startswith("affinites "):
        return "🌿 Bien-être et affinités"
    for label, names in CATEGORIES:
        if name in names or (" " not in name and name in names) or (name.startswith("giveaway ") and "giveaway" in names) or (name.startswith("affinites ") and "affinites" in names):
            return label
    return "🧰 Autres commandes"

def _parameter_text(parameter) -> str:
    name = getattr(parameter, "display_name", None) or getattr(parameter, "name", "paramètre")
    required = getattr(parameter, "required", False)
    token = f"<{name}>" if required else f"[{name}]"
    details = (getattr(parameter, "description", "") or "").strip()
    choices = getattr(parameter, "choices", None) or []
    if choices:
        options = ", ".join(str(choice.name) for choice in choices[:6])
        details = f"{details} Choix : {options}." if details else f"Choix : {options}."
    minimum = getattr(parameter, "min_value", None)
    maximum = getattr(parameter, "max_value", None)
    if minimum is not None or maximum is not None:
        bounds = f"{minimum if minimum is not None else '…'} à {maximum if maximum is not None else '…'}"
        details = f"{details} Limites : {bounds}." if details else f"Limites : {bounds}."
    return f"{token} — {details}" if details else token

def command_entries(bot) -> list[dict]:
    entries = []
    for command in bot.tree.walk_commands():
        if not isinstance(command, app_commands.Command):
            continue
        name = command.qualified_name
        leaf = command.name
        parameters = list(getattr(command, "parameters", []) or [])
        signature = f"/{name}" + ((" " + " ".join(
            f"<{getattr(p, 'display_name', None) or p.name}>" if getattr(p, "required", False)
            else f"[{getattr(p, 'display_name', None) or p.name}]"
            for p in parameters
        )) if parameters else "")
        staff = name in STAFF_ONLY or (" " not in name and leaf in STAFF_ONLY)
        access = "Équipe" if staff else MIXED_ACCESS.get(leaf, "Membres")
        permission = STAFF_PERMISSIONS.get(name, STAFF_PERMISSIONS.get(leaf, "")) if staff else ""
        if leaf in {"timeout", "untimeout"}:
            permission = "Permission Modérer les membres ou rôle staff habilité."
        elif leaf in {"avertir", "avertissements", "retirer_avertissement", "expulser", "bannir", "debannir", "purger", "note_membre"}:
            permission = "Rôle staff autorisé ou administrateur ; certaines actions exigent la permission Discord correspondante."
        elif leaf == "alerte_equipe":
            permission = "Réservée à l'équipe HORIZONS."
        elif leaf in {"tache_creer", "taches", "tache_statut"}:
            permission = "Prise de service obligatoire ; droits variables selon le rôle."
        entries.append({
            "name": name, "leaf": leaf, "signature": signature,
            "description": (command.description or "Commande HORIZONS.").strip(),
            "parameters": parameters, "parameter_text": [_parameter_text(p) for p in parameters],
            "staff": staff, "access": access, "permission": permission,
            "category": _category(name),
        })
    return sorted(entries, key=lambda item: (item["staff"], item["category"], item["name"]))

def build_catalog_embeds(bot, *, audience: str = "all", updated: str = "") -> list[discord.Embed]:
    """Construit les pages du guide à partir des commandes actuellement chargées."""
    entries = command_entries(bot)
    if audience == "members":
        entries = [e for e in entries if not e["staff"]]
        title = "✦ HORIZONS — Commandes des membres"
        intro = "Répertoire des commandes membres actuellement chargées. Les paramètres entre < > sont obligatoires ; ceux entre [ ] sont facultatifs. Les activités du carrefour HORIZONS (dont Petits Bonheurs et Mystère du jour) sont accessibles par menu, sans commande."
    elif audience == "staff":
        entries = [e for e in entries if e["staff"]]
        title = "✦ HORIZONS — Commandes de l'équipe"
        intro = "Répertoire des commandes staff actuellement chargées. L'accès reste contrôlé par le bot et les permissions Discord ; certaines fonctions exigent une prise de service. Le carrefour communautaire et ses activités ne nécessitent pas de commande slash supplémentaire."
    else:
        title = "✦ HORIZONS — Catalogue des commandes"
        intro = "🌌 **Pour commencer : `/centre`** ouvre ton espace personnel et privé, avec accueil personnalisé, Carte du Ciel et accès aux activités.\n\nRépertoire complet des commandes actuellement chargées. < > = obligatoire ; [ ] = facultatif."
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry["category"], []).append(entry)

    embeds: list[discord.Embed] = []
    current = horizons_embed(title=title, description=intro + (f"\nMise à jour : {updated}" if updated else ""))
    current.set_footer(text="HORIZONS • Nos différences nous rapprochent")
    for category, items in grouped.items():
        lines = []
        for entry in items:
            line = f"**`{entry['signature']}`**\n{entry['description']}"
            if entry["parameter_text"]:
                line += "\n" + "\n".join(f"• {p}" for p in entry["parameter_text"])
            if entry["permission"]:
                line += f"\n🔒 {entry['permission']}"
            elif entry["access"] != "Membres":
                line += f"\nℹ️ {entry['access']}"
            lines.append(line)
        chunks, buffer = [], ""
        for line in lines:
            candidate = f"{buffer}\n\n{line}" if buffer else line
            if len(candidate) > 950 and buffer:
                chunks.append(buffer)
                buffer = line
            else:
                buffer = candidate
        if buffer:
            chunks.append(buffer)
        for index, chunk in enumerate(chunks, 1):
            if len(current.fields) >= 12 or len(current) + len(chunk) + len(field_name if False else category) > 5300:
                embeds.append(current)
                current = horizons_embed(title=f"{title} — suite")
                current.set_footer(text="HORIZONS • Nos différences nous rapprochent")
            field_name = category + (f" (suite {index})" if index > 1 else "")
            current.add_field(name=field_name[:256], value=chunk[:1024], inline=False)
    if not current.fields:
        current.description += "\n\nAucune commande dans cette catégorie."
    current.set_footer(text=f"HORIZONS • {len(entries)} commande(s) • {updated or 'Catalogue actualisé'}")
    embeds.append(current)
    return embeds
