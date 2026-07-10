# 📜 NewsIQ Story Versioning & Audit Trail Specification

This document details the database schema, models, and execution patterns for tracking changes to news stories over time as new articles are merged.

---

## 1. Why Story Versioning?

As new articles are published, the clustering engine merges them into existing story entities, which triggers a regeneration of:
* Headlines and summaries (1-line, short, detailed).
* Timeline event structures.
* Entity arrays and tags.
* Source coverage statistics and contradiction lists.

To support client transparency, editorial review, and rollback capabilities, we must track the historical evolution of a story as a versioned audit trail.

---

## 2. Database Models

We introduce `StoryVersionModel` to store historical versions of stories:

```python
class StoryVersion(Base):
    """Historical snap-shots of story summaries and metadata."""
    
    __tablename__ = "story_versions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Summaries
    headline: Mapped[str] = mapped_column(String(255))
    one_line_summary: Mapped[str] = mapped_column(Text)
    short_summary: Mapped[str] = mapped_column(Text)
    detailed_summary: Mapped[str] = mapped_column(Text)
    
    # State snapshots
    knowledge_graph_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    article_ids_snapshot: Mapped[list[uuid.UUID]] = mapped_column(JSONB)  # List of merged article IDs
    
    # Versioning metadata
    trigger_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # The article merge that triggered this version
    updated_at: Mapped[datetime] = mapped_column(default=_now)
    editor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # Null if system-generated
    
    __table_args__ = (
        UniqueConstraint("story_id", "version", name="uq_story_id_version"),
    )
```

---

## 3. Version Commit Workflow

Whenever `generate_story_content` finishes successfully:

1. **Calculate New Version Number**: Query `SELECT COALESCE(MAX(version), 0) + 1 FROM story_versions WHERE story_id = :story_id`.
2. **Snapshot Current State**: Extract the current story headline, summaries, knowledge graph, and the list of associated article IDs.
3. **Write Version Record**: Insert a new `StoryVersion` row within the active transaction.
4. **Commit Transaction**: Commit both the updated `Story` record and the new `StoryVersion` record concurrently.

This guarantees that every update to a story has a corresponding entry in the version history, allowing users to view changes over time.
