"""Initial migration

Revision ID: 4971cd171d3d
Revises: 
Create Date: 2025-02-26 02:57:52.198268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4971cd171d3d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ltp_data',
    sa.Column('trading_symbol', sa.String(), nullable=False),
    sa.Column('ltp', sa.Float(), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('trading_symbol')
    )
    op.create_table('stock_exceptions',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('owner_type', sa.String(), nullable=False),
    sa.Column('trading_symbol', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('owner_id', 'owner_type', 'trading_symbol')
    )
    op.create_table('account_bracket_basket_allocation',
    sa.Column('owner_id', sa.String(), nullable=False),
    sa.Column('owner_type', sa.String(), nullable=False),
    sa.Column('basket_id', sa.Integer(), nullable=False),
    sa.Column('allocation_pct', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['basket_id'], ['basket_details.basket_id'], ),
    sa.PrimaryKeyConstraint('owner_id', 'owner_type', 'basket_id')
    )
    op.drop_column('account_actual_portfolio', 'month_end_date')
    op.alter_column('account_ideal_portfolio', 'trading_symbol',
               existing_type=sa.VARCHAR(),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('account_ideal_portfolio', 'basket',
               existing_type=sa.VARCHAR(),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('client_details', 'acc_start_date',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=True)
    op.drop_column('client_details', 'is_distributor')
    op.alter_column('joint_account', 'account_type',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=False,
               existing_server_default=sa.text("'joint'::text"))
    op.alter_column('pf_bracket_basket_allocation', 'bracket_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('pf_bracket_basket_allocation', 'basket_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('pf_bracket_basket_allocation', 'portfolio_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint('portfolio_bracket_basket_allocation_bracket_id_fkey', 'pf_bracket_basket_allocation', type_='foreignkey')
    op.drop_constraint('portfolio_bracket_basket_allocation_basket_id_fkey', 'pf_bracket_basket_allocation', type_='foreignkey')
    op.drop_constraint('portfolio_bracket_basket_allocation_portfolio_id_fkey', 'pf_bracket_basket_allocation', type_='foreignkey')
    op.create_foreign_key(None, 'pf_bracket_basket_allocation', 'basket_details', ['basket_id'], ['basket_id'])
    op.create_foreign_key(None, 'pf_bracket_basket_allocation', 'portfolio_template_details', ['portfolio_id'], ['portfolio_id'])
    op.create_foreign_key(None, 'pf_bracket_basket_allocation', 'bracket_details', ['bracket_id'], ['bracket_id'])
    op.alter_column('portfolio_basket_mapping', 'allocation_pct',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('single_account', 'account_type',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=False,
               existing_server_default=sa.text("'single'::text"))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('single_account', 'account_type',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=False,
               existing_server_default=sa.text("'single'::text"))
    op.alter_column('portfolio_basket_mapping', 'allocation_pct',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.drop_constraint(None, 'pf_bracket_basket_allocation', type_='foreignkey')
    op.drop_constraint(None, 'pf_bracket_basket_allocation', type_='foreignkey')
    op.drop_constraint(None, 'pf_bracket_basket_allocation', type_='foreignkey')
    op.create_foreign_key('portfolio_bracket_basket_allocation_portfolio_id_fkey', 'pf_bracket_basket_allocation', 'portfolio_template_details', ['portfolio_id'], ['portfolio_id'], ondelete='CASCADE')
    op.create_foreign_key('portfolio_bracket_basket_allocation_basket_id_fkey', 'pf_bracket_basket_allocation', 'basket_details', ['basket_id'], ['basket_id'], ondelete='CASCADE')
    op.create_foreign_key('portfolio_bracket_basket_allocation_bracket_id_fkey', 'pf_bracket_basket_allocation', 'bracket_details', ['bracket_id'], ['bracket_id'], ondelete='CASCADE')
    op.alter_column('pf_bracket_basket_allocation', 'portfolio_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('pf_bracket_basket_allocation', 'basket_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('pf_bracket_basket_allocation', 'bracket_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('joint_account', 'account_type',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=False,
               existing_server_default=sa.text("'joint'::text"))
    op.add_column('client_details', sa.Column('is_distributor', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True))
    op.alter_column('client_details', 'acc_start_date',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.alter_column('account_ideal_portfolio', 'basket',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('account_ideal_portfolio', 'trading_symbol',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.add_column('account_actual_portfolio', sa.Column('month_end_date', postgresql.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False))
    op.drop_table('account_bracket_basket_allocation')
    op.drop_table('stock_exceptions')
    op.drop_table('ltp_data')
    # ### end Alembic commands ###
