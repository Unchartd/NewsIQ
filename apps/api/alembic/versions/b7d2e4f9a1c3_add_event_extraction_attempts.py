"""add event extraction attempt counter and claim timestamp to articles

'failed' was terminal after a single attempt: the extraction selector only
picks up pending/NULL, so any error — including every provider in the chain
being down — removed the article from the pipeline for good. During one
Gemini quota outage with an invalid Bedrock key, 205 of 603 articles were
lost that way in three hours, and none of them could ever be clustered.

event_extraction_attempts lets a failed article go back to 'pending' until a
cap is reached, so only a repeatable failure is terminal.

event_extraction_started_at records when a run claimed the article. Stuck
'processing' recovery keyed on crawled_at/created_at, which is fine while
'processing' is never committed — but extraction now commits its claim so
that concurrent runs cannot select the same articles, and an article crawled
an hour ago and claimed a second ago must not be "recovered" mid-flight.

Additive: the counter is non-null with a server default of 0 and the
timestamp is nullable, so existing rows need no backfill. Rows already
'failed' are left as they are; resetting them is a separate, deliberate step.

Revision ID: b7d2e4f9a1c3
Revises: f1b6d3e90a24
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e4f9a1c3"
down_revision: str | None = "f1b6d3e90a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("event_extraction_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "articles",
        sa.Column("event_extraction_started_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("articles", "event_extraction_started_at")
    op.drop_column("articles", "event_extraction_attempts")
