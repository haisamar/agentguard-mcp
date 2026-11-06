begin;
create or replace function public.review_approval(p_approval_id text, p_reviewer text, p_decision text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare a public.approvals%rowtype; reviewed timestamptz;
begin
  if p_reviewer is null or p_reviewer not like 'human:_%' or p_decision is null or p_decision not in ('APPROVED','DENIED') then
    return jsonb_build_object('ok',false,'reason','Invalid review.');
  end if;
  select * into a from public.approvals where id=p_approval_id for update;
  if not found or a.status <> 'PENDING' then
    return jsonb_build_object('ok',false,'reason','Request is no longer pending or does not exist.');
  end if;
  reviewed := clock_timestamp();
  if p_decision='APPROVED' and (a.created_at <= reviewed - interval '1 hour' or a.created_at > reviewed) then
    return jsonb_build_object('ok',false,'reason','Request has expired or has an invalid creation time.');
  end if;
  update public.approvals set status=p_decision, reviewed_by=p_reviewer, reviewed_at=reviewed,
    approved_by=case when p_decision='APPROVED' then p_reviewer else null end,
    approved_at=case when p_decision='APPROVED' then reviewed else null end
  where id=a.id;
  insert into public.audit_events(identity,action,decision,reason,approval_id,metadata)
  values(p_reviewer,case when p_decision='APPROVED' then 'approve_action' else 'deny_action' end,
    case when p_decision='APPROVED' then 'APPROVED' else 'DENY' end,
    'Human administrator reviewed the request.',a.id,
    jsonb_build_object('source','agentguard_dashboard','actor_type','human'));
  return jsonb_build_object('ok',true,'approval_id',a.id,'status',p_decision);
end $$;
revoke all on function public.review_approval(text,text,text) from public,anon,authenticated;
grant execute on function public.review_approval(text,text,text) to service_role;
commit;

