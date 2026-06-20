# Event Normalization

> Phase 3 — Canonical event type taxonomy and synonym mapping

## Overview

Every extracted event type is normalized to a controlled vocabulary using the event taxonomy module. This ensures consistent event type classification across different articles, sources, and LLM outputs.

## Canonical Event Types

The taxonomy contains **14 top-level categories** and **~100 subtypes**:

| Category | Subtypes | Example Synonyms |
|:--|:--|:--|
| ATTACK | MISSILE_STRIKE, DRONE_ATTACK, BOMBING, etc. | "air assault", "shelling", "bombed" |
| DETENTION | ARREST, RAID, IMPRISONMENT, etc. | "arrested", "detained", "held", "taken into custody" |
| ELECTION | PRESIDENTIAL, PARLIAMENTARY, REFERENDUM, etc. | "elected", "voted", "polls" |
| AGREEMENT | MOU, TRADE_DEAL, PEACE_AGREEMENT, etc. | "deal", "pact", "accord", "signed agreement" |
| MERGER | ACQUISITION, TAKEOVER, BUYOUT, etc. | "merged", "acquired", "takeover" |
| NATURAL_DISASTER | EARTHQUAKE, TSUNAMI, FLOOD, etc. | "earthquake", "flooding", "wildfire" |
| PROTEST | DEMONSTRATION, RIOT, STRIKE_ACTION, etc. | "protested", "march", "rally" |
| LEGISLATION | BILL_PASSED, LAW_ENACTED, EXECUTIVE_ORDER, etc. | "bill passed", "regulation" |
| HEALTH | DISEASE_OUTBREAK, VACCINE, DRUG_APPROVAL, etc. | "outbreak", "pandemic", "vaccine" |
| LEGAL | LAWSUIT, VERDICT, INDICTMENT, etc. | "sued", "convicted", "sentenced" |
| ... | ... | ... |

## Normalization Strategy

```text
Raw Event Type (from LLM)
       ↓
  1. Exact match in taxonomy keys → Return
  2. Exact match in subtypes → Return subtype
  3. Synonym map lookup (case-insensitive) → Return canonical
  4. Partial match in synonyms → Return canonical
  5. Return as-is (with UPPER_CASE normalization)
```

## Implementation

- **Module**: `app/services/event_taxonomy.py`
- **Functions**:
  - `canonicalize_event_type(raw_type)` → canonical type string
  - `get_parent_type(event_type)` → parent category
  - `get_all_canonical_types()` → flat list of all types
- **Synonym Map**: ~200 entries mapping natural language phrases to canonical types

## Hierarchy

Each subtype maps to a parent:
```text
ATTACK (parent)
├── MISSILE_STRIKE
├── DRONE_ATTACK
├── AIR_STRIKE
├── BOMBING
└── ...
```

`get_parent_type("MISSILE_STRIKE")` → `"ATTACK"`

This hierarchy is used in clustering to determine if two events are of the same general type even if subtypes differ.
