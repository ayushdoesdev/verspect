"""Add provider-agnostic billing columns for Stripe + Razorpay.

Keeps existing stripe_* columns for compatibility and dual-writes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009_billing_multi_provider"
down_revision = "008_migration_rule_match_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "billing_provider",
            sa.String(length=32),
            nullable=False,
            server_default="stripe",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("billing_customer_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_organizations_billing_customer_id",
        "organizations",
        ["billing_customer_id"],
    )
    op.create_index(
        "ix_organizations_billing_provider",
        "organizations",
        ["billing_provider"],
    )

    # Backfill canonical customer id from Stripe column
    op.execute(
        sa.text(
            """
            UPDATE organizations
            SET billing_customer_id = stripe_customer_id,
                billing_provider = 'stripe'
            WHERE stripe_customer_id IS NOT NULL
            """
        )
    )

    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_provider",
            sa.String(length=32),
            nullable=False,
            server_default="stripe",
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_price_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_provider_subscription_id",
        "subscriptions",
        ["provider_subscription_id"],
    )
    op.create_index(
        "ix_subscriptions_billing_provider",
        "subscriptions",
        ["billing_provider"],
    )
    op.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET provider_subscription_id = stripe_subscription_id,
                provider_price_id = stripe_price_id,
                billing_provider = 'stripe'
            WHERE stripe_subscription_id IS NOT NULL
               OR stripe_price_id IS NOT NULL
            """
        )
    )

    op.add_column(
        "invoices",
        sa.Column(
            "billing_provider",
            sa.String(length=32),
            nullable=False,
            server_default="stripe",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column("provider_invoice_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_invoices_billing_provider",
        "invoices",
        ["billing_provider"],
    )
    op.create_index(
        "ix_invoices_provider_invoice_id",
        "invoices",
        ["provider_invoice_id"],
    )
    op.execute(
        sa.text(
            """
            UPDATE invoices
            SET provider_invoice_id = stripe_invoice_id,
                billing_provider = 'stripe'
            WHERE stripe_invoice_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_provider_invoice_id", table_name="invoices")
    op.drop_index("ix_invoices_billing_provider", table_name="invoices")
    op.drop_column("invoices", "provider_metadata")
    op.drop_column("invoices", "provider_invoice_id")
    op.drop_column("invoices", "billing_provider")

    op.drop_index("ix_subscriptions_billing_provider", table_name="subscriptions")
    op.drop_index("ix_subscriptions_provider_subscription_id", table_name="subscriptions")
    op.drop_column("subscriptions", "provider_payment_id")
    op.drop_column("subscriptions", "provider_price_id")
    op.drop_column("subscriptions", "provider_subscription_id")
    op.drop_column("subscriptions", "billing_provider")

    op.drop_index("ix_organizations_billing_provider", table_name="organizations")
    op.drop_index("ix_organizations_billing_customer_id", table_name="organizations")
    op.drop_column("organizations", "billing_customer_id")
    op.drop_column("organizations", "billing_provider")
