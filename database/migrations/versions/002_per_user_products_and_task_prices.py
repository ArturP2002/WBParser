"""Per-user products and per-task price history

Revision ID: 002_per_user_task_prices
Revises: 001_initial
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_per_user_task_prices"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_user_id_users",
        "products",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    n_users = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    if n_users:
        uid = bind.execute(sa.text("SELECT MIN(id) FROM users")).scalar()
        bind.execute(
            sa.text("UPDATE products SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": uid},
        )
    else:
        bind.execute(sa.text("DELETE FROM notifications"))
        bind.execute(sa.text("DELETE FROM product_prices"))
        bind.execute(sa.text("DELETE FROM product_sellers"))
        bind.execute(sa.text("DELETE FROM products"))
    bind.execute(sa.text("DELETE FROM products WHERE user_id IS NULL"))

    op.alter_column("products", "user_id", existing_type=sa.Integer(), nullable=False)

    op.drop_constraint("products_wb_id_key", "products", type_="unique")
    op.create_index("idx_products_user", "products", ["user_id"], unique=False)
    op.create_index(
        "uq_products_user_wb_id",
        "products",
        ["user_id", "wb_id"],
        unique=True,
    )

    op.create_table(
        "task_product_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["search_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_task_product_prices_lookup",
        "task_product_prices",
        ["task_id", "product_id"],
        unique=False,
    )

    op.add_column(
        "notifications",
        sa.Column("task_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_notifications_task_id_search_tasks",
        "notifications",
        "search_tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_notifications_task_dedup",
        "notifications",
        ["user_id", "task_id", "product_id", "price"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_task_dedup", table_name="notifications")
    op.drop_constraint("fk_notifications_task_id_search_tasks", "notifications", type_="foreignkey")
    op.drop_column("notifications", "task_id")

    op.drop_index("idx_task_product_prices_lookup", table_name="task_product_prices")
    op.drop_table("task_product_prices")

    op.drop_index("uq_products_user_wb_id", table_name="products")
    op.drop_index("idx_products_user", table_name="products")
    op.create_unique_constraint("products_wb_id_key", "products", ["wb_id"])
    op.drop_constraint("fk_products_user_id_users", "products", type_="foreignkey")
    op.drop_column("products", "user_id")
