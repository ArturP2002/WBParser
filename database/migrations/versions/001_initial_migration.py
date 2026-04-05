"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'], unique=False)
    
    # Create search_tasks table
    op.create_table(
        'search_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.String(length=500), nullable=False),
        sa.Column('price_min', sa.Integer(), nullable=True),
        sa.Column('price_max', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tasks_user', 'search_tasks', ['user_id'], unique=False)
    op.create_index('idx_tasks_active', 'search_tasks', ['is_active'], unique=False)
    
    # Create task_exclude_words table
    op.create_table(
        'task_exclude_words',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('word', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['search_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_exclude_task', 'task_exclude_words', ['task_id'], unique=False)
    
    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('wb_id', sa.BigInteger(), nullable=False),
        sa.Column('root_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=1000), nullable=True),
        sa.Column('normalized_name', sa.String(length=1000), nullable=True),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('seller', sa.String(length=255), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wb_id')
    )
    op.create_index('idx_products_wb_id', 'products', ['wb_id'], unique=False)
    op.create_index('idx_products_root', 'products', ['root_id'], unique=False)
    op.create_index('idx_products_normalized', 'products', ['normalized_name'], unique=False)
    
    # Create product_sellers table
    op.create_table(
        'product_sellers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('seller_name', sa.String(length=255), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_product_sellers', 'product_sellers', ['product_id'], unique=False)
    
    # Create product_prices table
    op.create_table(
        'product_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_prices_product', 'product_prices', ['product_id'], unique=False)
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notifications_user_product', 'notifications', ['user_id', 'product_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_notifications_user_product', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('idx_prices_product', table_name='product_prices')
    op.drop_table('product_prices')
    op.drop_index('idx_product_sellers', table_name='product_sellers')
    op.drop_table('product_sellers')
    op.drop_index('idx_products_normalized', table_name='products')
    op.drop_index('idx_products_root', table_name='products')
    op.drop_index('idx_products_wb_id', table_name='products')
    op.drop_table('products')
    op.drop_index('idx_exclude_task', table_name='task_exclude_words')
    op.drop_table('task_exclude_words')
    op.drop_index('idx_tasks_active', table_name='search_tasks')
    op.drop_index('idx_tasks_user', table_name='search_tasks')
    op.drop_table('search_tasks')
    op.drop_index('idx_users_telegram_id', table_name='users')
    op.drop_table('users')
