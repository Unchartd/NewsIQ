# NewsIQ Quality Evaluation Framework

To ensure that optimizations to the NewsIQ AI processing pipeline (such as context compression, model routing, and cost budgeting) do not degrade synthesis quality, the platform enforces a **Quality Evaluation Framework** powered by a curated "golden dataset."

---

## 1. Golden Dataset Structure

The golden dataset is located in `tests/golden/stories/` and consists of JSON files representing diverse news stories with expected outputs:

| Story File | Category | Factual Complexity | Key Features Tested |
|---|---|---|---|
| `politics_01.json` | `politics` | Medium | Named Entity Recognition (NER), tax numbers (15%) |
| `business_01.json` | `business` | High | Company entity linking, mega-merger details ($12B) |
| `disaster_01.json` | `world` | Critical | Contradicting casualty counts (50 vs 120 dead) |

---

## 2. Evaluation Metrics

During evaluation, the pipeline outputs are scored against expected golden criteria:

1. **Category Mapping Accuracy**: Bounded to 100% correct category mapping (e.g. tax reform must map to `politics`).
2. **Headline Keyword Precision**: Measures the overlap of expected keywords in the generated headline. Must be $\ge 50\%$.
3. **Entity Recall**: Checks that critical real-world entities are extracted and correctly linked. Must be $\ge 50\%$.
4. **Contradiction Recall**: Verifies that stories containing conflicting facts (e.g. disaster_01) successfully trigger the contradiction detection engine.

---

## 3. Regression Quality Gates

Before shipping any change to the synthesis pipeline:

1. **No Quality Regression**: The overall regression rate across all golden stories must be **exactly 0%**.
2. **Cost-to-Quality Ratio**: Any optimization that reduces cost must maintain quality metrics within $\pm 2\%$ of the baseline.
3. **Continuous Integration**: The golden evaluation suite is executed on every PR via pytest:
   ```bash
   $env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_golden_eval.py
   ```
