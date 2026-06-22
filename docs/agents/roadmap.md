# Agent & Gateway Roadmap

This document outlines future enhancements and optimizations planned for the NewsIQ Agno Agent registry and unified LLM Gateway.

## Phase 1: Local LLM Fallback (Ollama)

To reduce cloud API dependencies and allow offline development/emergency local fallbacks:
* **Integration**: Deploy `Ollama` as a service container inside the `docker-compose.yml`.
* **Models**: Support `llama3:8b` or `mistral:7b` for local verification.
* **Routing**: Add `ollama` as a provider client adapter inside the `ProviderPool` and place it in the fallback chain right before the `MockProvider`.

## Phase 2: Dynamic Prompt Versioning (DB-based)

Currently, prompts are written inline inside agent files. We plan to:
* Migrate prompts to a database table `prompt_templates`.
* Fetch the active prompt template at execution time based on the pipeline stage.
* Track prompt performance (A/B testing, version comparisons) using Langfuse analytics.

## Phase 3: Advanced Agent Tooling

Equip agents with specific tools to verify facts in real-time:
* **Knowledge Base Query**: Let agents search past events in the graph to check for historic context.
* **Wikipedia search**: Allow entity linking agents to query the Wikipedia/Wikidata Search API directly through the LLM Gateway.

## Phase 4: Reinforcement Fine-Tuning

Once we collect sufficient verified traces in `llm_traces`:
* Extract high-confidence success traces.
* Fine-tune a smaller local model (e.g., Llama-3-8B) on the exact inputs and outputs of the `Cluster Verification Agent`.
* Replace cloud models with the fine-tuned local model, achieving equivalent precision at a fraction of the cost.
