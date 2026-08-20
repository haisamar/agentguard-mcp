-- =========================================================
-- AgentGuard Database Schema
-- =========================================================


-- ---------------------------------------------------------
-- APPROVALS
-- Sensitive agent actions that may require human review.
-- ---------------------------------------------------------

create table if not exists public.approvals (
    id text primary key,

    requesting_identity text not null,
    action text not null,

    payload jsonb not null default '{}'::jsonb,
    reason text,

    status text not null default 'PENDING'
        check (
            status in (
                'PENDING',
                'APPROVED',
                'DENIED',
                'EXECUTED'
            )
        ),

    -- Generic review information.
    -- Used for both approvals and denials.
    reviewed_by text,
    reviewed_at timestamptz,

    -- Approval-specific information.
    -- Remains null when a request is denied.
    approved_by text,
    approved_at timestamptz,

    created_at timestamptz not null default now(),
    executed_at timestamptz
);


-- ---------------------------------------------------------
-- AUDIT EVENTS
-- Immutable-style security decision records written by
-- the AgentGuard backend and dashboard server actions.
-- ---------------------------------------------------------

create table if not exists public.audit_events (
    id uuid primary key default gen_random_uuid(),

    identity text not null,
    action text not null,
    decision text not null,

    required_scope text,
    reason text,

    approval_id text
        references public.approvals(id)
        on delete set null,

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);


-- ---------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------

create index if not exists approvals_status_idx
    on public.approvals(status);

create index if not exists approvals_identity_idx
    on public.approvals(requesting_identity);

create index if not exists approvals_reviewed_by_idx
    on public.approvals(reviewed_by);

create index if not exists approvals_created_at_idx
    on public.approvals(created_at desc);


create index if not exists audit_events_identity_idx
    on public.audit_events(identity);

create index if not exists audit_events_approval_id_idx
    on public.audit_events(approval_id);

create index if not exists audit_events_created_at_idx
    on public.audit_events(created_at desc);


-- ---------------------------------------------------------
-- ROW LEVEL SECURITY
--
-- No browser-facing policies are intentionally created.
-- AgentGuard accesses these tables only from trusted
-- server environments using a Supabase secret key.
-- ---------------------------------------------------------

alter table public.approvals enable row level security;
alter table public.audit_events enable row level security;