---
trigger: always_on
---

# documentation.md — Documentation Writing Rules for NewsIQ

These rules govern the creation, style, and lifecycle of system design documents, code comments, and technical guides.

## 1. Document Format & Mermaid Diagrams
- **Structure**: All documentation files must be written in GitHub Flavored Markdown (GFM).
- **Mermaid Usage**: Visualize flows, components, and pipelines using standard Mermaid syntax. Avoid nesting HTML tags inside node labels.
- **Code Links**: Always provide clickable file paths or line ranges when referring to specific source code assets.

## 2. In-Code Comments & ADRs
- **Docstrings**: Maintain strict docstring requirements for all public functions, classes, and REST routers.
- **ADR Lifecycle**: Create an Architecture Decision Record (ADR) in the docs folder for any major database, pipeline, or framework change, detailing the context, decisions, and trade-offs.
- **Comment Integrity**: Preserve existing comments and docstrings unless explicitly instructed to modify them.
