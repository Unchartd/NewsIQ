# Entity Extraction Redesign

> Phase 6 — 25+ entity types with LLM-primary extraction

## The Problem

The old NER service used `en_core_web_sm` (12MB) which only supports 4 entity types:
- PERSON, ORG, LOCATION, EVENT

The regex fallback **defaults everything unrecognized to PERSON**, causing:
- "MoU" → PERSON ❌ (should be AGREEMENT)
- "Andhra Pradesh" → PERSON ❌ (should be STATE)
- "Birzeit University" → PERSON ❌ (should be ORG)
- "Supreme Court" → PERSON ❌ (should be GOVERNMENT_BODY)

## Solution: NER v2

### Entity Types (25+)

| Type | Examples |
|:--|:--|
| PERSON | Narendra Modi, Joe Biden |
| ORG | United Nations, Red Cross |
| COMPANY | Google, Tesla, Meta |
| COUNTRY | India, United States, Israel |
| CITY | Mumbai, Washington DC |
| STATE | Andhra Pradesh, California |
| PLACE | Pentagon, Kremlin |
| LOCATION | Middle East, South Asia |
| EVENT | G20 Summit, Olympics |
| AGREEMENT | MoU, Paris Agreement |
| LAW | GDPR, Patriot Act |
| PRODUCT | iPhone, GPT-4 |
| TECHNOLOGY | CRISPR, blockchain |
| POLITICAL_PARTY | BJP, Democratic Party |
| WEAPON | HIMARS, Javelin |
| SHIP | USS Gerald Ford |
| AIRCRAFT | F-35, MiG-29 |
| DATE | June 2024 |
| TIME | 2:00 PM UTC |
| MONEY | $5.2 billion |
| PERCENTAGE | 3.5% |
| CRYPTO | Bitcoin, Ethereum |
| SPORTS_TEAM | Manchester United |
| DISEASE | COVID-19, Mpox |
| GOVERNMENT_BODY | Supreme Court, Parliament |
| MILITARY_UNIT | 82nd Airborne |

### Architecture

```text
Article Text
     ↓
  1. LLM Extraction (Gemini/OpenAI) ← Primary
     ↓
  2. Rules Post-Processing ← Corrections
     ↓
  3. spaCy Fallback ← If LLM fails
     ↓
  Normalized Entities
```

### Rules-Based Corrections

Even when using LLM extraction, rules-based post-processing catches known patterns:

| Pattern | Rule | Override To |
|:--|:--|:--|
| Indian state names (30+) | Exact match | STATE |
| US state names (50) | Exact match | STATE |
| University/college indicators | Contains keyword | ORG |
| Agreement patterns (MoU, treaty, etc.) | Contains keyword | AGREEMENT |
| Political party keywords | Contains keyword | POLITICAL_PARTY |

### Implementation

- **Service**: `app/services/ner_service_v2.py`
- **Singleton**: `ner_service_v2` (backward-compatible API)
- **Old service**: `ner_service` kept intact for rollback safety

### Backward Compatibility

The new service has the same public API:
```python
# Old
entities = ner_service.extract_entities(text)
# New (async)
entities = await ner_service_v2.extract_entities(text)
```

Both return: `[{"value": "Entity Name", "type": "PERSON", ...}]`
