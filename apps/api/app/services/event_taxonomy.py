"""Event taxonomy — canonical event types, synonyms, and hierarchy.

This module defines the controlled vocabulary for news event classification.
Every extracted event is normalized to one of these canonical types.

Design principles:
    - Broad enough to cover 95% of news events
    - Specific enough to prevent false-positive clustering
    - Hierarchical: ATTACK > MISSILE_STRIKE, AGREEMENT > MOU
    - LLM-assisted for edge cases not in the synonym map
"""

from __future__ import annotations

# ── Canonical Event Types ─────────────────────────────────────────────────────
# Top-level categories and their subtypes. The canonical form is the key.
# Format: CATEGORY_SUBTYPE or just CATEGORY for broad types.

EVENT_TAXONOMY: dict[str, list[str]] = {
    # ── Conflict & Security ───────────────────────────────────────────────────
    "ATTACK": [
        "MISSILE_STRIKE", "DRONE_ATTACK", "AIR_STRIKE", "BOMBING",
        "SHELLING", "SHOOTING", "STABBING", "AMBUSH", "SUICIDE_ATTACK",
        "CYBER_ATTACK", "TERRORIST_ATTACK",
    ],
    "MILITARY_OPERATION": [
        "INVASION", "GROUND_OFFENSIVE", "NAVAL_OPERATION",
        "BLOCKADE", "CEASEFIRE", "WITHDRAWAL", "DEPLOYMENT",
    ],
    "DETENTION": [
        "ARREST", "RAID", "IMPRISONMENT", "EXTRADITION",
        "HOSTAGE_TAKING", "KIDNAPPING",
    ],
    "PROTEST": [
        "DEMONSTRATION", "RIOT", "STRIKE_ACTION", "CIVIL_DISOBEDIENCE",
        "OCCUPATION", "MARCH", "RALLY",
    ],
    "VIOLENCE": [
        "ASSASSINATION", "MURDER", "MASS_SHOOTING", "HATE_CRIME",
        "POLICE_BRUTALITY", "ETHNIC_VIOLENCE",
    ],

    # ── Politics & Governance ─────────────────────────────────────────────────
    "ELECTION": [
        "PRESIDENTIAL_ELECTION", "PARLIAMENTARY_ELECTION", "LOCAL_ELECTION",
        "REFERENDUM", "PRIMARY", "RUNOFF",
    ],
    "LEGISLATION": [
        "BILL_PASSED", "BILL_PROPOSED", "LAW_ENACTED", "EXECUTIVE_ORDER",
        "REGULATION", "AMENDMENT", "REPEAL", "VETO",
    ],
    "POLICY": [
        "POLICY_ANNOUNCEMENT", "REFORM", "BAN", "TARIFF",
        "SUBSIDY", "TAX_CHANGE",
    ],
    "SANCTIONS": [
        "ECONOMIC_SANCTIONS", "TRADE_EMBARGO", "ASSET_FREEZE",
        "TRAVEL_BAN", "ARMS_EMBARGO",
    ],
    "DIPLOMACY": [
        "SUMMIT", "STATE_VISIT", "TREATY", "PEACE_TALKS",
        "MEDIATION", "RECOGNITION", "RECALL_AMBASSADOR",
    ],
    "AGREEMENT": [
        "MOU", "TRADE_DEAL", "PEACE_AGREEMENT", "CEASEFIRE_AGREEMENT",
        "BILATERAL_AGREEMENT", "MULTILATERAL_AGREEMENT", "CONTRACT",
    ],

    # ── Business & Economy ────────────────────────────────────────────────────
    "MERGER": ["ACQUISITION", "TAKEOVER", "BUYOUT", "JOINT_VENTURE"],
    "IPO": ["LISTING", "DELISTING", "STOCK_SPLIT"],
    "EARNINGS": ["QUARTERLY_RESULTS", "ANNUAL_REPORT", "PROFIT_WARNING"],
    "LAYOFF": ["RESTRUCTURING", "DOWNSIZING", "HIRING_FREEZE"],
    "BANKRUPTCY": ["INSOLVENCY", "LIQUIDATION", "DEBT_DEFAULT"],
    "PRODUCT_LAUNCH": ["ANNOUNCEMENT", "RELEASE", "RECALL"],
    "INVESTMENT": ["FUNDING_ROUND", "VENTURE_CAPITAL", "PRIVATE_EQUITY"],

    # ── Disaster & Environment ────────────────────────────────────────────────
    "NATURAL_DISASTER": [
        "EARTHQUAKE", "TSUNAMI", "HURRICANE", "TORNADO", "FLOOD",
        "WILDFIRE", "VOLCANIC_ERUPTION", "LANDSLIDE", "DROUGHT",
    ],
    "WEATHER": [
        "EXTREME_HEAT", "EXTREME_COLD", "STORM", "BLIZZARD",
        "HEATWAVE", "CYCLONE",
    ],
    "ACCIDENT": [
        "PLANE_CRASH", "TRAIN_DERAILMENT", "INDUSTRIAL_ACCIDENT",
        "BUILDING_COLLAPSE", "EXPLOSION", "SHIPWRECK",
    ],
    "ENVIRONMENTAL": [
        "OIL_SPILL", "POLLUTION", "DEFORESTATION",
        "CLIMATE_REPORT", "EMISSIONS",
    ],

    # ── Science & Technology ──────────────────────────────────────────────────
    "DISCOVERY": ["SCIENTIFIC_BREAKTHROUGH", "MEDICAL_DISCOVERY", "ARCHAEOLOGICAL_FIND"],
    "SPACE": ["LAUNCH", "LANDING", "SPACE_MISSION", "SATELLITE"],
    "AI_TECH": ["AI_MODEL_RELEASE", "AI_REGULATION", "AI_BREAKTHROUGH"],
    "HEALTH": [
        "DISEASE_OUTBREAK", "PANDEMIC", "VACCINE", "DRUG_APPROVAL",
        "HEALTH_ADVISORY", "RECALL_DRUG",
    ],

    # ── Sports ────────────────────────────────────────────────────────────────
    "SPORTS": [
        "MATCH", "TOURNAMENT", "CHAMPIONSHIP", "TRANSFER",
        "INJURY", "DOPING", "RECORD", "RETIREMENT",
    ],

    # ── Social & Culture ──────────────────────────────────────────────────────
    "DEATH": ["OBITUARY", "EXECUTION"],
    "AWARD": ["PRIZE", "HONOR", "RECOGNITION_AWARD"],
    "SCANDAL": ["CORRUPTION", "FRAUD", "COVER_UP"],
    "LEGAL": [
        "LAWSUIT", "VERDICT", "INDICTMENT", "SETTLEMENT",
        "APPEAL", "RULING", "INVESTIGATION",
    ],

    # ── Catch-all ─────────────────────────────────────────────────────────────
    "OTHER": [],
}

# ── Synonym Map ───────────────────────────────────────────────────────────────
# Maps natural-language phrases (lowercase) → canonical event type.
# Used for fast rule-based canonicalization before falling back to LLM.

SYNONYM_MAP: dict[str, str] = {
    # Conflict
    "arrested": "DETENTION",
    "detained": "DETENTION",
    "held": "DETENTION",
    "taken into custody": "DETENTION",
    "apprehended": "DETENTION",
    "captured": "DETENTION",
    "raided": "DETENTION",
    "extradited": "DETENTION",
    "missile strike": "ATTACK",
    "drone attack": "ATTACK",
    "air assault": "ATTACK",
    "air strike": "ATTACK",
    "airstrike": "ATTACK",
    "bombardment": "ATTACK",
    "shelled": "ATTACK",
    "shelling": "ATTACK",
    "bombed": "ATTACK",
    "bombing": "ATTACK",
    "shot": "ATTACK",
    "shooting": "ATTACK",
    "stabbing": "ATTACK",
    "ambush": "ATTACK",
    "suicide attack": "ATTACK",
    "terror attack": "ATTACK",
    "terrorist attack": "ATTACK",
    "cyber attack": "ATTACK",
    "hacked": "ATTACK",
    "invaded": "MILITARY_OPERATION",
    "invasion": "MILITARY_OPERATION",
    "ground offensive": "MILITARY_OPERATION",
    "ceasefire": "MILITARY_OPERATION",
    "troops deployed": "MILITARY_OPERATION",
    "withdrawal": "MILITARY_OPERATION",
    "blockade": "MILITARY_OPERATION",
    "assassinated": "VIOLENCE",
    "murdered": "VIOLENCE",
    "killed": "VIOLENCE",
    "mass shooting": "VIOLENCE",
    "lynched": "VIOLENCE",

    # Politics
    "elected": "ELECTION",
    "voted": "ELECTION",
    "polls": "ELECTION",
    "referendum": "ELECTION",
    "primary election": "ELECTION",
    "bill passed": "LEGISLATION",
    "law enacted": "LEGISLATION",
    "executive order": "LEGISLATION",
    "regulation": "LEGISLATION",
    "sanctioned": "SANCTIONS",
    "sanctions imposed": "SANCTIONS",
    "trade embargo": "SANCTIONS",
    "asset freeze": "SANCTIONS",
    "summit": "DIPLOMACY",
    "state visit": "DIPLOMACY",
    "peace talks": "DIPLOMACY",
    "treaty signed": "DIPLOMACY",
    "agreement": "AGREEMENT",
    "deal": "AGREEMENT",
    "mou": "AGREEMENT",
    "memorandum of understanding": "AGREEMENT",
    "signed agreement": "AGREEMENT",
    "trade deal": "AGREEMENT",
    "peace deal": "AGREEMENT",
    "pact": "AGREEMENT",
    "accord": "AGREEMENT",
    "protested": "PROTEST",
    "demonstration": "PROTEST",
    "riot": "PROTEST",
    "strike": "PROTEST",
    "march": "PROTEST",
    "rally": "PROTEST",
    "sit-in": "PROTEST",

    # Business
    "merged": "MERGER",
    "merger": "MERGER",
    "acquired": "MERGER",
    "acquisition": "MERGER",
    "takeover": "MERGER",
    "buyout": "MERGER",
    "ipo": "IPO",
    "went public": "IPO",
    "listed": "IPO",
    "delisted": "IPO",
    "laid off": "LAYOFF",
    "layoffs": "LAYOFF",
    "restructuring": "LAYOFF",
    "downsizing": "LAYOFF",
    "bankruptcy": "BANKRUPTCY",
    "insolvent": "BANKRUPTCY",
    "defaulted": "BANKRUPTCY",
    "launched": "PRODUCT_LAUNCH",
    "released": "PRODUCT_LAUNCH",
    "unveiled": "PRODUCT_LAUNCH",
    "announced": "PRODUCT_LAUNCH",
    "recalled": "PRODUCT_LAUNCH",
    "funding round": "INVESTMENT",
    "raised capital": "INVESTMENT",
    "venture capital": "INVESTMENT",
    "quarterly results": "EARNINGS",
    "reported earnings": "EARNINGS",
    "profit warning": "EARNINGS",

    # Disaster
    "earthquake": "NATURAL_DISASTER",
    "tsunami": "NATURAL_DISASTER",
    "hurricane": "NATURAL_DISASTER",
    "tornado": "NATURAL_DISASTER",
    "flood": "NATURAL_DISASTER",
    "flooding": "NATURAL_DISASTER",
    "wildfire": "NATURAL_DISASTER",
    "volcanic eruption": "NATURAL_DISASTER",
    "landslide": "NATURAL_DISASTER",
    "drought": "NATURAL_DISASTER",
    "storm": "WEATHER",
    "blizzard": "WEATHER",
    "heatwave": "WEATHER",
    "heat wave": "WEATHER",
    "cyclone": "WEATHER",
    "extreme heat": "WEATHER",
    "extreme cold": "WEATHER",
    "plane crash": "ACCIDENT",
    "crashed": "ACCIDENT",
    "derailed": "ACCIDENT",
    "train derailment": "ACCIDENT",
    "explosion": "ACCIDENT",
    "collapsed": "ACCIDENT",
    "building collapse": "ACCIDENT",

    # Science & Health
    "outbreak": "HEALTH",
    "pandemic": "HEALTH",
    "vaccine": "HEALTH",
    "drug approved": "HEALTH",
    "fda approved": "HEALTH",
    "clinical trial": "HEALTH",
    "launched rocket": "SPACE",
    "space mission": "SPACE",
    "satellite": "SPACE",
    "landed on": "SPACE",

    # Legal
    "sued": "LEGAL",
    "lawsuit": "LEGAL",
    "verdict": "LEGAL",
    "indicted": "LEGAL",
    "indictment": "LEGAL",
    "convicted": "LEGAL",
    "acquitted": "LEGAL",
    "sentenced": "LEGAL",
    "ruling": "LEGAL",
    "appeal": "LEGAL",
    "investigation": "LEGAL",
    "settled": "LEGAL",

    # Other
    "died": "DEATH",
    "passed away": "DEATH",
    "obituary": "DEATH",
    "awarded": "AWARD",
    "won prize": "AWARD",
    "scandal": "SCANDAL",
    "corruption": "SCANDAL",
    "fraud": "SCANDAL",
}


def get_all_canonical_types() -> list[str]:
    """Return a flat list of all canonical event types (parents + children)."""
    types = list(EVENT_TAXONOMY.keys())
    for subtypes in EVENT_TAXONOMY.values():
        types.extend(subtypes)
    return types


def canonicalize_event_type(raw_type: str) -> str:
    """Normalize a raw event type string to a canonical type.

    Strategy:
        1. Exact match against taxonomy keys/subtypes
        2. Synonym map lookup
        3. Return as-is (LLM should have already normalized)
    """
    if not raw_type:
        return "OTHER"

    normalized = raw_type.strip().upper().replace(" ", "_").replace("-", "_")

    # 1. Exact match in taxonomy
    if normalized in EVENT_TAXONOMY:
        return normalized

    # 2. Check subtypes
    for parent, children in EVENT_TAXONOMY.items():
        if normalized in children:
            return normalized  # Return the specific subtype

    # 3. Synonym map (case-insensitive)
    lower = raw_type.strip().lower()
    if lower in SYNONYM_MAP:
        return SYNONYM_MAP[lower]

    # 4. Partial match in synonyms
    for phrase, canonical in SYNONYM_MAP.items():
        if phrase in lower or lower in phrase:
            return canonical

    return normalized if normalized else "OTHER"


def get_parent_type(event_type: str) -> str:
    """Get the parent category for a subtype. Returns itself if already a parent."""
    normalized = event_type.strip().upper().replace(" ", "_").replace("-", "_")

    if normalized in EVENT_TAXONOMY:
        return normalized

    for parent, children in EVENT_TAXONOMY.items():
        if normalized in children:
            return parent

    return "OTHER"
