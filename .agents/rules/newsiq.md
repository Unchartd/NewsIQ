---
trigger: always_on
---

# NewsIQ Project Constitution

You are working on **NewsIQ**, a production-grade AI News Intelligence Platform.

Your objective is not simply to write code. Your responsibility is to continuously improve the platform while preserving correctness, scalability, maintainability, and cost efficiency.

---

# Core Principles

Always optimize for:
- Production readiness
- Long-term maintainability
- Reliability
- Scalability
- Performance
- Observability
- Cost efficiency
- Developer experience

Never prioritize short-term convenience over long-term architecture.

---

# Understand Before Acting

Before making changes:
- Understand the user's objective.
- Understand the affected feature.
- Identify impacted modules.
- Read existing implementations before creating new ones.
- Reuse existing abstractions whenever possible.

Never implement features based on assumptions.
If project context is insufficient, investigate the repository first.

---

# Respect Existing Architecture

NewsIQ is built around modular pipelines.
Preserve clear boundaries between:
- Ingestion
- Parsing
- Event Extraction
- Clustering
- Story Synthesis
- Reflection
- Knowledge Graph
- API
- Frontend
- Observability

Never introduce unnecessary coupling between pipelines.

---

# AI-First Engineering

NewsIQ is an AI system, not just a CRUD application.
Every AI-related change must consider:
- inference cost
- latency
- caching
- evaluation
- reproducibility
- confidence
- fallback behavior

Never introduce unnecessary LLM calls.
Prefer deterministic logic whenever it produces equivalent results.
LLMs should augment deterministic systems, not replace them.

---

# Cost Awareness

Every new AI feature has an operational cost.
Before adding:
- prompts
- embeddings
- reranking
- summarization
- extraction
- synthesis

consider:
- Can existing results be reused?
- Can Redis cache it?
- Can semantic cache answer it?
- Can this run offline?
- Can this execute asynchronously?
- Can batching reduce cost?

Every unnecessary LLM request is technical debt.

---

# Data Integrity

Never compromise data quality.
Prefer:
- immutable events
- deterministic processing
- idempotent operations
- reproducible pipelines

Never silently discard information.
Always preserve source attribution.

---

# Story Integrity

NewsIQ represents real-world events.
Never:
- merge unrelated stories
- fabricate missing information
- hide conflicting facts
- remove uncertainty

Always preserve:
- source references
- timestamps
- confidence
- provenance

When sources disagree, surface the disagreement instead of guessing.

---

# Performance

Always consider:
- database queries
- Redis usage
- Qdrant lookups
- API latency
- memory usage
- worker throughput

Avoid:
- repeated database queries
- repeated embeddings
- repeated LLM calls
- duplicate processing

---

# Observability

Every critical pipeline should be observable.
Prefer:
- structured logging
- metrics
- tracing
- execution timing
- failure reporting

Failures should be diagnosable without reproducing production traffic.

---

# Security

Never:
- expose secrets
- hardcode credentials
- bypass authentication
- trust external input

Validate all external data.
Sanitize AI inputs where appropriate.

---

# Documentation

Whenever architecture changes:
Update the relevant documentation.
Architecture decisions should be documented.
Public API changes should update API documentation.
Keep diagrams synchronized with implementation.

---

# Testing

Appropriate tests should accompany production changes.
Prefer regression tests for bug fixes.
Critical pipeline logic should be verifiable without relying solely on LLM outputs.

---

# Refactoring

Improve code when it meaningfully increases:
- readability
- modularity
- maintainability
- reliability

Avoid unnecessary rewrites.
Preserve public interfaces unless explicitly changing them.

---

# Decision Making

When multiple valid solutions exist:
Choose the solution that best balances:
1. Correctness
2. Maintainability
3. Scalability
4. Performance
5. Cost
6. Simplicity

Explain significant architectural trade-offs before implementing them.

---

# Scope Discipline

Solve the requested problem completely.
Avoid unrelated refactoring unless it:
- fixes a bug,
- removes clear technical debt,
- or is required for the implementation.

Keep pull requests focused.

---

# Definition of Done

A task is complete only when:
- the implementation is production-ready,
- architecture remains consistent,
- existing functionality is preserved,
- appropriate tests have been added or updated,
- documentation has been updated where necessary,
- no obvious technical debt has been introduced.

Always leave the codebase in a better state than you found it.
