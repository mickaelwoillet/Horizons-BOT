"""Règles éditoriales *déterministes* de la veille HORIZONS.

Pas d'inférence de mobile discriminatoire ou de synthèse d'article non consulté.
Le titre RSS reste une attribution au média, pas une affirmation du bot.
"""
from __future__ import annotations

import re
import html
import unicodedata
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# Sources vérifiables et connues; une source absente ne devient jamais fiable par défaut.
TRUSTED_DOMAINS = frozenset({
    'lemonde.fr','francetvinfo.fr','franceinfo.fr','radiofrance.fr',
    'francebleu.fr','ici.fr','france24.com','liberation.fr','lefigaro.fr',
    'ouest-france.fr','sudouest.fr','lavoixdunord.fr','leparisien.fr',
    'la-croix.com','20minutes.fr','bfmtv.com','rtl.fr','tf1info.fr',
    'actu.fr','mediapart.fr','publicsenat.fr','franceinter.fr',
    'francetv.fr','defenseurdesdroits.fr','cncdh.fr','gouv.fr',
    'service-public.fr','justice.fr','sos-homophobie.org','dilcrah.gouv.fr',
    'humanite.fr','courrierinternational.com','franceculture.fr',
    'lesechos.fr','lepoint.fr','huffingtonpost.fr','euronews.com',
    'rfi.fr','tv5monde.com',
})
DISCRIMINATION_WORDS = (
    'racis','xénophob','xenophob','homophob','transphob','antisémi','antisemi',
    'islamophob','discrimin','haine anti','lgbt','handicap','sexism',
    'antimusulman','anti-musulman','antichrétien','anti-chretien',
    'validism','negrophob','négrophob','religion','ethni',
)
POSITIVE_WORDS = (
    'solidarit','inclusi','égalité','egalité','entraide','mobilisation',
    'sensibilis','toléran','toleran','soutien','association','initiative',
    'lutte contre','prévention','prevention','marche pour',
)
SENSITIVE_WORDS = (
    'meurtre','assassinat','suicide','viol ','agression','blessé','blesse',
    'décès','deces','attentat','violence','menace de mort','homicide',
)
STOPWORDS = set('de la le les des du pour avec dans sur une un aux et en au par a à l d ce cette ces est son sa ses contre en france français française nouveau nouvelle devant après devant selon elle il qui que quoi quand affaire lors plus moins leur leurs fait faits'.split())


def normalize(text: str) -> str:
    raw = unicodedata.normalize('NFKD', text.casefold())
    return ''.join(c for c in raw if not unicodedata.combining(c))


def publisher_domain(source_url: str) -> str:
    try:
        parsed = urlparse(source_url)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            return ''
        return (parsed.hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''


def trusted_source(source_url: str, extra_domains=()) -> bool:
    domain = publisher_domain(source_url)
    return bool(domain) and any(domain == root or domain.endswith('.'+root)
        for root in (TRUSTED_DOMAINS | frozenset(extra_domains)))


def relevant_headline(title: str, category: str) -> bool:
    text = normalize(title)
    indicators = tuple(normalize(w) for w in DISCRIMINATION_WORDS)
    positive = tuple(normalize(w) for w in POSITIVE_WORDS)
    if category == 'Solidarité':
        # Une initiative positive doit être explicitement reliée à l'inclusion.
        return any(p in text for p in positive) and (
            any(w in text for w in indicators) or any(x in text for x in ('diversite','vivre ensemble','difference','egalite'))
        )
    return any(w in text for w in indicators)


def news_date(value: str):
    try:
        result = parsedate_to_datetime(value)
        return result.astimezone(timezone.utc) if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError, IndexError):
        return None


def within_recent_days(stamp, today, max_days: int = 3) -> bool:
    if stamp is None: return False
    date = stamp.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Paris')).date()
    return today - timedelta(days=max_days) <= date <= today



def feed_excerpt(description: str, title: str) -> str:
    """Extrait du flux RSS, pas un résumé inventé de l'article complet.

    Google News reprend parfois seulement le titre, auquel cas on n'ajoute rien.
    """
    txt=html.unescape(re.sub(r'<[^>]*>', ' ', description or ''))
    txt=re.sub(r'\s+', ' ', txt).strip()
    if len(txt)<80 or len(txt)>5000:return ''
    title_text=normalize(title.rsplit(' - ',1)[0])
    brief=normalize(txt)
    # Écarter les flux qui répètent simplement le titre et le nom du journal.
    if title_text and title_text in brief and len(brief)-len(title_text)<70:return ''
    if any(x in txt.lower() for x in ('javascript:', 'data:text/html')):return ''
    return txt[:260] + ('…' if len(txt)>260 else '')

def meaningful_tokens(title: str) -> set[str]:
    title = title.rsplit(' - ', 1)[0]
    return {token for token in re.findall(r'[a-z0-9]{4,}', normalize(title))
        if token not in STOPWORDS}


def same_story(a: str, b: str, *, threshold: float = .78) -> bool:
    first, second = meaningful_tokens(a), meaningful_tokens(b)
    if len(first) < 4 or len(second) < 4: return False
    intersection = first & second
    return len(intersection) >= 4 and len(intersection) / len(first | second) >= threshold


# Identifiants de sujets/personnalités récurrents : une seule actualité par
# protagoniste et par édition, même si les titres emploient des mots différents.
# Les groupes sont explicites afin de ne pas confondre des sujets sur le seul
# thème général (racisme, justice, discrimination...).
EDITORIAL_SUBJECTS = {
    'marine-le-pen': ('marine le pen', 'marine lepen'),
    'eric-zemmour': ('eric zemmour', 'zemmour'),
    'jordan-bardella': ('jordan bardella', 'bardella'),
    'donald-trump': ('donald trump', 'trump'),
}

def editorial_subject(title: str) -> str:
    text = ' '.join(normalize(title).split())
    for subject, aliases in EDITORIAL_SUBJECTS.items():
        if any(normalize(alias) in text for alias in aliases):
            return subject
    return ''

def editorial_duplicate(a: str, b: str) -> bool:
    """Regroupe les titres quasi identiques ou centrés sur le même protagoniste.

    Un même thème général ne suffit pas à déclarer deux sujets identiques.
    """
    a_subject, b_subject = editorial_subject(a), editorial_subject(b)
    return bool(a_subject and a_subject == b_subject) or same_story(a, b, threshold=.58)


def followup_story(a: str, b: str) -> bool:
    """Lien uniquement en cas de ressemblance très forte; pas de rapprochement spéculatif."""
    first, second = meaningful_tokens(a), meaningful_tokens(b)
    return (len(first & second) >= 5 and
            len(first & second) / max(len(first), len(second), 1) >= .72)


def news_score(title: str, category: str, published_at: str = '') -> int:
    words=normalize(title)
    strong=('condamn','tribunal','justice','enquet','plainte','agression','discrimin','racis','homophob','transphob','antisemi','islamophob')
    score = sum(2 for term in strong if term in words)
    if category == 'Solidarité' and any(normalize(x) in words for x in POSITIVE_WORDS): score += 3
    if published_at: score += 1
    return score


def article_card(row, followup_url: str = '') -> str:
    """Brève sourcée et lisible, sans simuler la lecture de l'article complet."""
    from discord.utils import escape_markdown
    title = escape_markdown(str(row['title']).rsplit(' - ', 1)[0][:210])
    category = escape_markdown(str(row['category'])[:55])
    source = escape_markdown(str(row['source'] or 'Média identifié')[:65])
    pub = str(row['published_at'])[:10] if row['published_at'] else ''
    lines = [f'**{title}**', f'🗞️ {source}  ·  {category}' + (f'  ·  {pub}' if pub else '')]
    summary = str(row['summary'] or '').strip()
    if summary:
        lines.append('\n' + escape_markdown(summary[:260]))
    if any(normalize(x) in normalize(row['title']) for x in SENSITIVE_WORDS):
        lines.append('⚠️ Sujet sensible')
    # Le lien court masque la longue URL Google News ; suppress_embeds=True
    # est utilisé lors de l'envoi pour éviter les cartes d'aperçu répétitives.
    lines.append(f'\n🔗 [Lire la source]({row["url"]})')
    if followup_url:
        lines.append(f'🔄 [Précédent sujet associé]({followup_url})')
    return '\n'.join(lines)[:1900]


def support_resources() -> str:
    return ('🤝 **Comment agir ?** En cas de discrimination, renseigne-toi auprès du '
            '**Défenseur des droits** : https://www.defenseurdesdroits.fr/ '
            'ou de **Service-Public** : https://www.service-public.fr/ . '
            'N’identifie personne publiquement et ne relaie pas de rumeurs.')
