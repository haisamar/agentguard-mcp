begin;
create table public.refund_requests (
 identity text not null, request_id text not null, payload jsonb not null,
 result jsonb not null, created_at timestamptz not null default clock_timestamp(),
 primary key(identity,request_id)
);
alter table public.refund_requests enable row level security;
revoke all on public.refund_requests from public,anon,authenticated;
grant select on public.refund_requests to service_role;
create function public.submit_refund_request(p_identity text,p_request_id text,p_account_id text,p_amount_minor bigint,p_currency text,p_reason text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare payload jsonb; prior public.refund_requests%rowtype; result jsonb; aid text;
begin
 if coalesce(p_identity,'')='' or p_request_id is null or p_request_id !~ '^[a-zA-Z0-9_-]{1,128}$'
 or p_account_id is null or p_account_id not in ('acct_001','acct_002','acct_003')
 or p_amount_minor is null or p_amount_minor<=0 or p_amount_minor>99999999999900
 or p_currency is distinct from 'USD' or p_reason is null or length(btrim(p_reason))=0 or length(p_reason)>2000 then
 return jsonb_build_object('decision','DENY','reason','Invalid v2 refund request.'); end if;
 payload:=jsonb_build_object('contract_version',2,'account_id',p_account_id,'amount_minor',p_amount_minor,
 'amount',p_amount_minor::numeric/100,'currency',p_currency,'reason',p_reason);
 -- Shared with autonomous budget RPC: serialize lookup, spending and result.
 perform pg_advisory_xact_lock(741931250);
 select * into prior from public.refund_requests where identity=p_identity and request_id=p_request_id;
 if found then
 if prior.payload is distinct from payload then
 return jsonb_build_object('decision','DENY','reason','Request ID already belongs to a different transaction.');
 end if;
 return prior.result;
 end if;
 if p_amount_minor<=50000 then
 result:=public.record_autonomous_refund(p_identity,p_account_id,p_amount_minor::numeric/100);
 else
 result:=jsonb_build_object('decision','APPROVAL_REQUIRED','reason','Refunds above $500 require human approval.');
 end if;
 if result->>'decision'='APPROVAL_REQUIRED' then
 aid:='apr_'||replace(gen_random_uuid()::text,'-','');
 insert into public.approvals(id,requesting_identity,action,payload,reason)
 values(aid,p_identity,'issue_refund',payload,result->>'reason');
 insert into public.audit_events(identity,action,decision,required_scope,reason,approval_id,metadata)
 values(p_identity,'issue_refund','APPROVAL_REQUIRED','finance:refund',result->>'reason',aid,
 jsonb_build_object('request_id',p_request_id,'contract_version',2));
 result:= result||jsonb_build_object('approval_id',aid,'status','pending_human_approval');
 end if;
 if result->>'decision' not in ('ALLOW','APPROVAL_REQUIRED','DENY') or result->>'decision' is null then
 raise exception 'Invalid refund transaction result'; end if;
 result:=result||jsonb_build_object('request_id',p_request_id,'contract_version',2);
 insert into public.refund_requests(identity,request_id,payload,result) values(p_identity,p_request_id,payload,result);
 return result;
end $$;
revoke all on function public.submit_refund_request(text,text,text,bigint,text,text) from public,anon,authenticated;
grant execute on function public.submit_refund_request(text,text,text,bigint,text,text) to service_role;
commit;

