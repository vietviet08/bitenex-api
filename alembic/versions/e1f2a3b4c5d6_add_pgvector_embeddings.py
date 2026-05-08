"""add pgvector embeddings for semantic search

Revision ID: e1f2a3b4c5d6
Revises: 334718eb712d
Create Date: 2026-05-07 12:00:00.000000

Changes:
- Enable pgvector extension
- Add embedding vector(1536) column to menu_items
- Add embedding vector(1536) column to merchants
- Create HNSW indexes for fast cosine similarity search
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "334718eb712d"
branch_labels = None
depends_on = None

VECTOR_DIMS = 1536  # text-embedding-3-small


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # Enable pgvector extension (idempotent)
    # ---------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---------------------------------------------------------------------
    # Add embedding column to menu_items
    # ---------------------------------------------------------------------
    op.add_column(
        "menu_items",
        sa.Column(
            "embedding",
            Vector(VECTOR_DIMS),
            nullable=True,
            comment="OpenAI text-embedding-3-small vector for semantic search",
        ),
    )

    # HNSW index on menu_items for fast cosine similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_menu_items_embedding_hnsw
        ON menu_items
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL
        """
    )

    # ---------------------------------------------------------------------
    # Add embedding column to merchants
    # ---------------------------------------------------------------------
    op.add_column(
        "merchants",
        sa.Column(
            "embedding",
            Vector(VECTOR_DIMS),
            nullable=True,
            comment="OpenAI text-embedding-3-small vector for semantic restaurant search",
        ),
    )

    # HNSW index on merchants for fast cosine similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_merchants_embedding_hnsw
        ON merchants
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS ix_menu_items_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_merchants_embedding_hnsw")

    # Drop embedding columns
    op.drop_column("menu_items", "embedding")
    op.drop_column("merchants", "embedding")

    # Note: We intentionally do NOT drop the vector extension here
    # as other tables might depend on it in the future.
