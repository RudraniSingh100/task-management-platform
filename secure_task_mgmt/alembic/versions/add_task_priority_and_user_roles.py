"""Add task priority and user roles

Revision ID: 8e0d7a4c2f90
Revises: 20f8cd2525e3
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8e0d7a4c2f90"
down_revision = "20f8cd2525e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default="medium",
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "priority")
    op.drop_column("users", "role")
