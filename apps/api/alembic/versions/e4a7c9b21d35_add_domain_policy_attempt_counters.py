"""add attempt counters to domain_extraction_policies

DomainExtractionPolicy stored only exponential moving averages of each
provider's success rate. Those cannot distinguish "failed once, on its first
ever attempt" from "failed fifty times in a row" — both read 0.0 — so the
table could never be used for routing without risking banishing a brand-new
domain to a paid provider on one unlucky timeout.

Production has 878 domains at local_success_rate = 0 out of 2789. Those
articles each burn three local attempts (up to 105s of timeouts) before
falling through. Routing around them needs a trustworthy sample count.

Additive and non-null with a server default of 0, so existing rows simply
start counting from their next extraction.

Revision ID: e4a7c9b21d35
Revises: d9f2e7b41c08
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4a7c9b21d35"
down_revision: str | None = "d9f2e7b41c08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("local_attempts", "tavily_attempts", "firecrawl_attempts")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column(
            "domain_extraction_policies",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.drop_column("domain_extraction_policies", column)
