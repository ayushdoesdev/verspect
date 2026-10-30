"""SaaS foundations — organizations, billing, auth identity fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "004_saas_foundations"
down_revision = "003_migration_kb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("plan", sa.String(32), server_default="free", nullable=False),
        sa.Column("is_personal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])
    op.create_index("ix_organizations_plan", "organizations", ["plan"])
    op.create_index("ix_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"])

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), server_default="developer", nullable=False),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    op.create_table(
        "organization_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), server_default="developer", nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "email", name="uq_org_invite_email"),
    )
    op.create_index("ix_organization_invitations_token", "organization_invitations", ["token"], unique=True)
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"])

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(32), server_default="free", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("billing_interval", sa.String(16), server_default="month", nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("seat_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_subscriptions_plan", "subscriptions", ["plan"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=True),
        sa.Column("number", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), server_default="open", nullable=False),
        sa.Column("amount_due", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(8), server_default="usd", nullable=False),
        sa.Column("hosted_invoice_url", sa.Text(), nullable=True),
        sa.Column("invoice_pdf", sa.Text(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("stripe_invoice_id"),
    )

    # User identity expansions
    op.alter_column("users", "github_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.String(32), server_default="github", nullable=False))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("email_verification_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("password_reset_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("onboarding_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("active_organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    op.create_index("ix_users_email_verification_token", "users", ["email_verification_token"])
    op.create_index("ix_users_password_reset_token", "users", ["password_reset_token"])
    op.create_foreign_key(
        "fk_users_active_org",
        "users",
        "organizations",
        ["active_organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "repositories",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_repositories_organization_id", "repositories", ["organization_id"])
    op.create_foreign_key(
        "fk_repositories_organization",
        "repositories",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_repositories_organization", "repositories", type_="foreignkey")
    op.drop_index("ix_repositories_organization_id", table_name="repositories")
    op.drop_column("repositories", "organization_id")

    op.drop_constraint("fk_users_active_org", "users", type_="foreignkey")
    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_index("ix_users_google_id", table_name="users")
    for col in (
        "active_organization_id",
        "onboarding_completed",
        "password_reset_expires_at",
        "password_reset_token",
        "email_verification_token",
        "email_verified",
        "auth_provider",
        "password_hash",
        "google_id",
    ):
        op.drop_column("users", col)
    op.alter_column("users", "github_id", existing_type=sa.Integer(), nullable=False)

    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("organization_invitations")
    op.drop_table("organization_members")
    op.drop_table("organizations")
