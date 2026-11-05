-- Apply in the AgentGuard Supabase project only.
-- Sandbox ledger: records simulated refunds, never sends real payments.
begin;

create table if not exists public.refund_receipts (
    id uuid primary key default gen_random_uuid(),
    approval_id text not null unique references public.approvals(id),
    identity text not null,
    account_id text not null,
    amount_minor bigint not null check (amount_minor > 0),
    currency text not null default 'USD' check (currency = 'USD'),
    simulated boolean not null default true check (simulated),
    created_at timestamptz not null default now()
);
alter table public.refund_receipts enable row level security;
revoke all on public.refund_receipts from anon, authenticated;
grant select on public.refund_receipts to service_role;

create or replace function public.execute_refund_with_receipt(
    p_approval_id text, p_identity text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    a public.approvals%rowtype;
    receipt public.refund_receipts%rowtype;
    amount_value numeric;
begin
    select * into a from public.approvals
    where id = p_approval_id for update;
    if not found then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Approval not found.');
    end if;
    if a.requesting_identity is distinct from p_identity then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Approval belongs to a different identity.');
    end if;
    if a.status <> 'APPROVED' or a.action <> 'issue_refund' then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Approval is not available for refund execution.');
    end if;
    if a.created_at is null or a.created_at <= clock_timestamp() - interval '1 hour' then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Approval has expired.');
    end if;
    if a.approved_by is null or a.approved_at is null then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Approval review record is incomplete.');
    end if;
    if jsonb_typeof(a.payload->'amount') is distinct from 'number'
       or coalesce(a.payload->>'account_id', '') = '' then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Invalid refund payload.');
    end if;
    amount_value := (a.payload->>'amount')::numeric;
    if amount_value <= 0 or amount_value > 999999999999
       or amount_value * 100 <> trunc(amount_value * 100) then
        return jsonb_build_object('decision', 'DENY', 'reason', 'Invalid USD amount or precision.');
    end if;

    insert into public.refund_receipts(approval_id, identity, account_id, amount_minor)
    values (a.id, p_identity, a.payload->>'account_id', (amount_value * 100)::bigint)
    returning * into receipt;

    update public.approvals set status = 'EXECUTED', executed_at = receipt.created_at
    where id = a.id;

    insert into public.audit_events(identity, action, decision, required_scope, reason, approval_id, metadata)
    values(p_identity, 'execute_approved_refund', 'ALLOW', 'finance:refund',
           'Approved sandbox refund recorded atomically.', a.id,
           jsonb_build_object('receipt_id', receipt.id, 'simulated', true));

    return jsonb_build_object('decision', 'ALLOW', 'status', 'simulated_refund_recorded',
                             'receipt_id', receipt.id, 'approval_id', a.id,
                             'amount_minor', receipt.amount_minor, 'currency', receipt.currency,
                             'simulated', true);
end;
$$;

revoke all on function public.execute_refund_with_receipt(text, text) from public, anon, authenticated;
grant execute on function public.execute_refund_with_receipt(text, text) to service_role;
commit;
