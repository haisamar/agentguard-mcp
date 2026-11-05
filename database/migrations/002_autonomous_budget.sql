begin;
create table public.autonomous_refund_receipts (
    id uuid primary key default gen_random_uuid(),
    identity text not null,
    account_id text not null,
    amount_minor bigint not null check (amount_minor > 0),
    currency text not null default 'USD' check (currency = 'USD'),
    simulated boolean not null default true check (simulated),
    created_at timestamptz not null default clock_timestamp()
);
create index autonomous_refund_created_idx on public.autonomous_refund_receipts(created_at);
alter table public.autonomous_refund_receipts enable row level security;
revoke all on public.autonomous_refund_receipts from anon, authenticated;
grant select on public.autonomous_refund_receipts to service_role;

create function public.record_autonomous_refund(p_identity text, p_account_id text, p_amount numeric)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare spent bigint; receipt public.autonomous_refund_receipts%rowtype;
begin
    if coalesce(p_identity, '') = '' or p_account_id not in ('acct_001','acct_002','acct_003') or p_account_id is null
       or p_amount is null or p_amount::text in ('NaN','Infinity','-Infinity')
       or p_amount <= 0 or p_amount > 500 or p_amount * 100 <> trunc(p_amount * 100) then
        return jsonb_build_object('decision','DENY','reason','Invalid autonomous refund payload.');
    end if;
    -- One deployment-wide budget across identities and accounts. Serialize check + write.
    perform pg_advisory_xact_lock(741931250);
    select coalesce(sum(amount_minor),0) into spent from public.autonomous_refund_receipts
    where created_at > clock_timestamp() - interval '24 hours';
    if spent + (p_amount * 100)::bigint > 50000 then
        return jsonb_build_object('decision','APPROVAL_REQUIRED','reason','Deployment-wide $500 rolling 24-hour autonomous refund budget exceeded.');
    end if;
    insert into public.autonomous_refund_receipts(identity,account_id,amount_minor)
    values(p_identity,p_account_id,(p_amount*100)::bigint) returning * into receipt;
    insert into public.audit_events(identity,action,decision,required_scope,reason,metadata)
    values(p_identity,'issue_refund','ALLOW','finance:refund','Sandbox refund within deployment-wide rolling budget.',
           jsonb_build_object('receipt_id',receipt.id,'simulated',true,'amount_minor',receipt.amount_minor));
    return jsonb_build_object('decision','ALLOW','status','simulated_refund_recorded','receipt_id',receipt.id,
                             'amount_minor',receipt.amount_minor,'currency','USD','simulated',true);
end $$;
revoke all on function public.record_autonomous_refund(text,text,numeric) from public,anon,authenticated;
grant execute on function public.record_autonomous_refund(text,text,numeric) to service_role;
commit;
