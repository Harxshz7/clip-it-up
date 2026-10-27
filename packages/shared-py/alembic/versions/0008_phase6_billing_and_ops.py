"""0008 phase6 billing, ledger, invoices, legal, abuse and operations

Revision ID: 0008_phase6_billing_and_ops
Revises: 0007_phase5_editor
Create Date: 2026-10-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_phase6_billing_and_ops"
down_revision: str | None = "0007_phase5_editor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Alter users table
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("is_suspended", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("status", sa.String(length=32), server_default="active", nullable=False))
    op.add_column("users", sa.Column("survey_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("users", sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Alter jobs table
    op.add_column("jobs", sa.Column("priority", sa.Integer(), server_default="1", nullable=False))
    op.add_column("jobs", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("jobs", sa.Column("stage_heartbeat", sa.DateTime(timezone=True), nullable=True))

    # 3. Alter plans table
    op.add_column("plans", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("plans", sa.Column("price_inr_monthly", sa.Integer(), server_default="0", nullable=False))
    op.add_column("plans", sa.Column("price_usd_monthly", sa.Integer(), server_default="0", nullable=False))
    op.add_column("plans", sa.Column("monthly_source_minutes", sa.Integer(), server_default="30", nullable=False))
    op.add_column("plans", sa.Column("watermark", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("plans", sa.Column("max_video_length_min", sa.Integer(), server_default="15", nullable=False))
    op.add_column("plans", sa.Column("max_concurrent_jobs", sa.Integer(), server_default="1", nullable=False))
    op.add_column("plans", sa.Column("retention_days", sa.Integer(), server_default="7", nullable=False))
    op.add_column("plans", sa.Column("priority", sa.String(length=32), server_default="normal", nullable=False))
    op.add_column("plans", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("plans", sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("plans", sa.Column("razorpay_plan_id", sa.String(length=128), nullable=True))
    op.add_column("plans", sa.Column("stripe_price_id", sa.String(length=128), nullable=True))

    # 4. Alter user_plans table
    op.add_column("user_plans", sa.Column("period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_plans", sa.Column("status", sa.String(length=32), server_default="active", nullable=False))
    op.add_column("user_plans", sa.Column("auto_renew", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column(
        "user_plans", sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column("user_plans", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))

    # 5. customers table
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_customers_user_provider"),
    )
    op.create_index("ix_customers_provider_cust_id", "customers", ["provider", "provider_customer_id"], unique=False)
    op.create_index("ix_customers_user_id", "customers", ["user_id"], unique=False)

    # 6. subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=False),
        sa.Column("plan_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_key"], ["plans.key"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_subscription_id", name="uq_subscriptions_provider_sub_id"),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"], unique=False)
    op.create_index(
        "ix_subscriptions_provider_sub_id", "subscriptions", ["provider", "provider_subscription_id"], unique=False
    )

    # 7. invoices table
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("financial_year", sa.String(length=16), nullable=False),
        sa.Column("seq_number", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), server_default="tax_invoice", nullable=False),
        sa.Column("original_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("customer_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("customer_gstin", sa.String(length=32), nullable=True),
        sa.Column("customer_state_code", sa.String(length=10), nullable=True),
        sa.Column("place_of_supply", sa.String(length=32), server_default="intra_state", nullable=False),
        sa.Column("taxable_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cgst_rate", sa.Numeric(precision=6, scale=4), server_default="0.0000", nullable=False),
        sa.Column("cgst_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("sgst_rate", sa.Numeric(precision=6, scale=4), server_default="0.0000", nullable=False),
        sa.Column("sgst_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("igst_rate", sa.Numeric(precision=6, scale=4), server_default="0.0000", nullable=False),
        sa.Column("igst_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("total_tax", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="paid", nullable=False),
        sa.Column("pdf_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("lut_note", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["original_invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number", name="uq_invoices_invoice_number"),
        sa.UniqueConstraint("financial_year", "seq_number", "type", name="uq_invoice_fy_seq_type"),
    )
    op.create_index("ix_invoices_user_created", "invoices", ["user_id", "created_at"], unique=False)
    op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)

    # 8. invoice_sequences table
    op.create_table(
        "invoice_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("financial_year", sa.String(length=16), nullable=False),
        sa.Column("seq_type", sa.String(length=32), server_default="tax_invoice", nullable=False),
        sa.Column("last_val", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix", "financial_year", "seq_type", name="uq_invoice_seq_prefix_fy_type"),
    )

    # 9. payments table
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="succeeded", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_payment_id", name="uq_payments_provider_payment_id"),
    )
    op.create_index("ix_payments_user_created", "payments", ["user_id", "created_at"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)

    # 10. webhook_events table
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="received", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event_id"),
    )
    op.create_index("ix_webhook_events_created", "webhook_events", ["created_at"], unique=False)

    # 11. top_ups table
    op.create_table(
        "top_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_key", sa.String(length=64), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_top_ups_user_status_exp", "top_ups", ["user_id", "status", "expires_at"], unique=False)

    # 12. quota_ledger table
    op.create_table(
        "quota_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delta_minutes", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=128), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quota_ledger_user_created", "quota_ledger", ["user_id", "created_at"], unique=False)
    op.create_index("ix_quota_ledger_reason", "quota_ledger", ["reason"], unique=False)

    # 13. invite_codes table
    op.create_table(
        "invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("uses_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_invite_codes_code"),
    )

    # 14. user_invites table
    op.create_table(
        "user_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invite_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invite_code_id"], ["invite_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_invites_user_id"),
    )

    # 15. terms_acceptances table
    op.create_table(
        "terms_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False),
        sa.Column("doc_version", sa.String(length=32), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_terms_acceptances_user_doc", "terms_acceptances", ["user_id", "doc_type", "doc_version"], unique=False
    )

    # 16. takedown_requests table
    op.create_table(
        "takedown_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.String(length=64), nullable=False),
        sa.Column("claimant_name", sa.String(length=255), nullable=False),
        sa.Column("claimant_email", sa.String(length=255), nullable=False),
        sa.Column("claimant_organization", sa.String(length=255), nullable=True),
        sa.Column("work_description", sa.Text(), nullable=False),
        sa.Column("infringing_url_or_id", sa.String(length=1024), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("good_faith_confirmed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("perjury_confirmed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("signature", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="submitted", nullable=False),
        sa.Column("counter_notice_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actioned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_trail", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actioned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_number", name="uq_takedown_requests_ticket_number"),
    )
    op.create_index("ix_takedown_requests_created_status", "takedown_requests", ["created_at", "status"], unique=False)

    # 17. deletion_audits table
    op.create_table(
        "deletion_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending_grace", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("s3_objects_deleted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("db_rows_deleted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("audit_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deletion_audits_entity", "deletion_audits", ["entity_type", "entity_id"], unique=False)

    # 18. dead_letter_jobs table
    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failed_stage", sa.String(length=64), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_dead_letter_jobs_job_id"),
    )
    op.create_index("ix_dead_letter_jobs_created", "dead_letter_jobs", ["created_at"], unique=False)

    # 19. analytics_events table
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_name_created", "analytics_events", ["event_name", "created_at"], unique=False)

    # 20. app_config_flags table
    op.create_table(
        "app_config_flags",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_config_flags")
    op.drop_table("analytics_events")
    op.drop_table("dead_letter_jobs")
    op.drop_table("deletion_audits")
    op.drop_table("takedown_requests")
    op.drop_table("terms_acceptances")
    op.drop_table("user_invites")
    op.drop_table("invite_codes")
    op.drop_table("quota_ledger")
    op.drop_table("top_ups")
    op.drop_table("webhook_events")
    op.drop_table("payments")
    op.drop_table("invoice_sequences")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("customers")
    op.drop_column("user_plans", "canceled_at")
    op.drop_column("user_plans", "cancel_at_period_end")
    op.drop_column("user_plans", "auto_renew")
    op.drop_column("user_plans", "status")
    op.drop_column("user_plans", "period_end")
    op.drop_column("plans", "stripe_price_id")
    op.drop_column("plans", "razorpay_plan_id")
    op.drop_column("plans", "is_public")
    op.drop_column("plans", "is_active")
    op.drop_column("plans", "priority")
    op.drop_column("plans", "retention_days")
    op.drop_column("plans", "max_concurrent_jobs")
    op.drop_column("plans", "max_video_length_min")
    op.drop_column("plans", "watermark")
    op.drop_column("plans", "monthly_source_minutes")
    op.drop_column("plans", "price_usd_monthly")
    op.drop_column("plans", "price_inr_monthly")
    op.drop_column("plans", "description")
    op.drop_column("jobs", "stage_heartbeat")
    op.drop_column("jobs", "attempts")
    op.drop_column("jobs", "priority")
    op.drop_column("users", "deletion_scheduled_at")
    op.drop_column("users", "survey_response")
    op.drop_column("users", "status")
    op.drop_column("users", "is_suspended")
    op.drop_column("users", "is_admin")
