# 🧮 NewsIQ Similarity Engine Code Review & Design

This document reviews the mathematical and logical fixes implemented in the multi-signal event similarity engine to prevent false-positive story merges.

---

## 1. Actor & Target Jaccard Similarity (Issue 8)

### The Mathematical Bug
Jaccard Similarity measures the overlap between two sets:

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

In the original Python implementation:
```python
actor_sim = 1.0
a1 = set(evt1.actors or [])
a2 = set(evt2.actors or [])
if a1 or a2:
    actor_sim = len(a1.intersection(a2)) / len(a1.union(a2)) if a1.union(a2) else 0.0
```

If both `evt1.actors` and `evt2.actors` were empty (`[]`), the condition `if a1 or a2:` was skipped, and `actor_sim` remained at its default value of `1.0`.
This resulted in two events with no extracted actors (e.g., due to parser extraction failures) being matched with a perfect similarity of `1.0` for actors. The same bug affected target similarity.

### The Corrected Logic
If either set is empty, or if both sets are empty, similarity must default to `0.0`. Jaccard similarity is only computed if *both* sets contain items:

```python
# Actor Similarity Corrected
a1 = set(evt1.actors or [])
a2 = set(evt2.actors or [])
if a1 and a2:
    actor_sim = len(a1.intersection(a2)) / len(a1.union(a2))
else:
    actor_sim = 0.0
```

This guarantees Jaccard similarity evaluates to `0.0` when actor information is missing, preventing false-positive matches on empty profiles.

---

## 2. Event Time Similarity (Issue 10)

### The Time Gap Bug
The time similarity calculation defaulted to `0.8` if either event time was missing. Under this setup, events separated by months or years could easily merge if their actors and locations matched.

### The Corrected Logic
Time similarity should only be `1.0` if events occurred on the same day. If events occurred on different days, similarity drops to `0.0`. If one or both event times are missing, similarity defaults to `0.5` (representing neutral uncertainty):

```python
# Event Time Similarity Corrected
if not evt1.event_time or not evt2.event_time:
    time_sim = 0.5
elif evt1.event_time.date() == evt2.event_time.date():
    time_sim = 1.0
else:
    time_sim = 0.0
```

---

## 3. Final Multi-Signal Similarity Formula

The direct event similarity is computed using the following weights:

| Signal | Component Weight | Base Metric |
| :--- | :--- | :--- |
| **Actor Similarity** | 25% | Jaccard Similarity on actor lists (0.0 if empty) |
| **Target Similarity** | 20% | Jaccard Similarity on target lists (0.0 if empty) |
| **Location Similarity** | 20% | Strict string matches (1.0), partial matches (0.8), or mismatch (0.0) |
| **Event Type Similarity** | 15% | Canonical match (1.0), shared category parent (0.5), mismatch (0.0) |
| **Time Similarity** | 10% | Same day (1.0), missing time (0.5), different day (0.0) |
| **Entity Overlap** | 10% | Calculated externally and added to overall score |
