"""Reject extracted "content" that is page furniture rather than an article.

Every extractor in the chain accepted any non-empty string as success, and the
last-resort BeautifulSoup cleaner returns `soup.get_text()` for the whole page.
So when the real article body could not be located — JS-rendered pages, consent
walls, Google News redirect shims — the pipeline happily stored the page chrome
instead. Measured in production: 541 of 2,225 articles in 24h (24%) held
navigation menus or cookie-consent text, averaging 31,903 characters against
6,637 for genuine articles.

That is worse than a failed crawl. The text is embedded, so those articles
cluster by site template rather than by topic, and events are extracted from
GDPR boilerplate.

The checks are deliberately structural (link density, line shape, phrase
density) rather than a blocklist of sites, and every rejection carries a reason
so the failure is visible in metrics instead of silent.
"""

import re

# Phrases that essentially never appear in article body text but dominate
# consent walls, paywalls and bot challenges.
_BOILERPLATE_MARKERS = (
    "continue without agreeing",
    "we and our partners",
    "cookies or similar technologies",
    "store and/or access information on a device",
    "manage your cookie",
    "accept all cookies",
    "your privacy choices",
    "legitimate business interest",
    "please enable javascript",
    "enable javascript to",
    "turn on javascript",
    "subscribe to continue reading",
    "sign in to continue",
    "create a free account to",
    "you have reached your article limit",
    "checking your browser",
    "verify you are a human",
    "are you a robot",
    "access to this page has been denied",
)

# A real article has prose. These indicate a link farm / nav dump.
_MARKDOWN_LINK = re.compile(r"\]\(\s*(?:https?:|blob:|javascript:)", re.I)
_RAW_URL = re.compile(r"https?://\S+")
_SENTENCE_END = re.compile(r"[.!?][\s\"')\]]")

MIN_ARTICLE_CHARS = 400
# Links per 1,000 characters. Genuine articles cite a handful of sources;
# navigation dumps carry dozens.
MAX_LINK_DENSITY_PER_KCHAR = 12.0
# Fraction of characters that must sit in sentence-shaped prose.
MIN_SENTENCES_PER_KCHAR = 1.5


def assess_article_content(text: str | None, *, title: str | None = None) -> tuple[bool, str]:
    """Return (is_article, reason).

    reason is "ok" when accepted, otherwise a short machine-usable slug so
    rejections can be counted per cause.
    """
    if not text or not text.strip():
        return False, "empty"

    body = text.strip()
    length = len(body)

    if length < MIN_ARTICLE_CHARS:
        return False, "too_short"

    lowered = body.lower()

    # Consent/paywall/challenge pages. Checked against the opening section as
    # well as the whole body: a consent wall front-loads its boilerplate, while
    # an article merely mentioning cookies in passing does not.
    head = lowered[:1500]
    for marker in _BOILERPLATE_MARKERS:
        if marker in head:
            return False, "boilerplate_wall"

    marker_hits = sum(1 for marker in _BOILERPLATE_MARKERS if marker in lowered)
    if marker_hits >= 2:
        return False, "boilerplate_wall"

    # Link farms: navigation dumps are mostly anchors.
    link_count = len(_MARKDOWN_LINK.findall(body)) + len(_RAW_URL.findall(body))
    link_density = link_count / (length / 1000.0)
    if link_density > MAX_LINK_DENSITY_PER_KCHAR:
        return False, "link_farm"

    # Prose check: page chrome is fragments and labels, not sentences.
    sentence_density = len(_SENTENCE_END.findall(body)) / (length / 1000.0)
    if sentence_density < MIN_SENTENCES_PER_KCHAR:
        return False, "not_prose"

    return True, "ok"
