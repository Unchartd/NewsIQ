# NewsIQ Quality Evaluation Framework

To ensure that optimizations to the NewsIQ AI processing pipeline (such as context compression, model routing, and cost budgeting) do not degrade synthesis quality, the platform enforces a **Quality Evaluation Framework** powered by a curated golden dataset and automated evaluation script.

---

## 1. Golden Dataset Structure

The golden dataset is stored in [dataset.json](file:///c:/Users/zakau/NewsIQ/apps/api/tests/golden/dataset.json) and consists of curated multi-article news scenarios:

- **Scenario ID & Description**: Context and scenario name.
- **Articles**: Mocked titles, descriptions, and full content for ingestion.
- **Expected Headline Keywords**: Ground-truth keywords that must appear in the final summary headline.
- **Expected Category**: Target category slug from `CATEGORY_SLUGS`.
- **Min Key Facts**: Target number of key facts generated.
- **Forbidden Words**: Hallucination checks or generic system prompt leak words.

---

## 2. Evaluation Metrics & Scoring

The runner evaluates the pipeline outputs on a 0-100% scale using the following sub-scores:

1. **Category Mapping Accuracy (33.3%)**: 100% score if the generated category matches target category; 0% otherwise.
2. **Headline Keyword Precision (33.3%)**: Ratio of expected keywords found in the generated headline.
3. **Key Facts Coverage (33.3%)**: Checks if key facts count satisfies the expected minimum requirement.
4. **Forbidden Words Penalty**: A strict `-20` point penalty is subtracted for each forbidden word found in the output.

The final scenario score is the average of the sub-scores minus any penalties. Scenarios scoring $\ge 80\%$ are marked as **PASSED**.

---

## 3. Automated Runner & CI Quality Gates

The quality evaluation suite is executed locally or via CI pipelines:

```bash
# Execute evaluation in simulated mode
$env:PYTHONPATH="."; .\.venv\Scripts\python tests/golden/eval_runner.py

# Execute evaluation in live LLM mode
$env:NEWS_AI_EVAL_LIVE=true; $env:PYTHONPATH="."; .\.venv\Scripts\python tests/golden/eval_runner.py
```

### Outputs & Observability
- **JSON Report**: Saved to [evaluation_report.json](file:///c:/Users/zakau/NewsIQ/apps/api/evaluation_report.json) detailing scores, metrics, and generated content for each scenario.
- **Prometheus Metrics**:
  - `newsiq_eval_summary_score` (labelled by `scenario_id`): Average quality score per scenario.
  - `newsiq_eval_pass_rate`: Percentage of passed scenarios.
- **Quality Gate**: The run fails (exit code 1) if the overall scenario pass rate is below 80.0%.
