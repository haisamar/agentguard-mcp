begin;
alter table public.approvals drop constraint approvals_status_check;
alter table public.approvals add constraint approvals_status_check
check(status in ('PENDING','APPROVED','DENIED','EXECUTED','CANCELLED'));

create table public.execution_control(
 id integer primary key check(id=1), paused boolean not null,
 updated_at timestamptz not null default clock_timestamp(), updated_by text
);
insert into public.execution_control(id,paused) values(1,false);
alter table public.execution_control enable row level security;
revoke all on public.execution_control from public,anon,authenticated;
grant select on public.execution_control to service_role;

create function public.set_execution_pause(p_paused boolean,p_reviewer text)
returns jsonb language plpgsql security definer set search_path='' as $$
begin
 if p_paused is null or p_reviewer is null or p_reviewer not like 'human:_%' then
 return jsonb_build_object('ok',false,'reason','Invalid administrator operation.'); end if;
 perform pg_advisory_xact_lock(741931250);
 update public.execution_control set paused=p_paused,updated_by=p_reviewer,updated_at=clock_timestamp() where id=1;
 if not found then raise exception 'Execution control is missing'; end if;
 insert into public.audit_events(identity,action,decision,reason,metadata)
 values(p_reviewer,'set_execution_pause',case when p_paused then 'PAUSED' else 'RESUMED' end,
 'Human administrator changed sandbox execution state.',jsonb_build_object('paused',p_paused));
 return jsonb_build_object('ok',true,'paused',p_paused);
end $$;
revoke all on function public.set_execution_pause(boolean,text) from public,anon,authenticated;
grant execute on function public.set_execution_pause(boolean,text) to service_role;

create function public.enforce_execution_pause() returns trigger
language plpgsql security definer set search_path='' as $$
declare paused_value boolean;
begin
 perform pg_advisory_xact_lock(741931250);
 select paused into paused_value from public.execution_control where id=1;
 if paused_value is distinct from false then
 raise exception 'Sandbox execution is paused or unavailable' using errcode='23514';
 end if;
 return new;
end $$;
revoke all on function public.enforce_execution_pause() from public,anon,authenticated;
create trigger enforce_autonomous_pause before insert on public.autonomous_refund_receipts
for each row execute function public.enforce_execution_pause();
create trigger enforce_approved_pause before insert on public.refund_receipts
for each row execute function public.enforce_execution_pause();

create function public.cancel_approval(p_approval_id text,p_reviewer text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare a public.approvals%rowtype;
begin
 if p_reviewer is null or p_reviewer not like 'human:_%' then
 return jsonb_build_object('ok',false,'reason','Invalid administrator identity.'); end if;
 select * into a from public.approvals where id=p_approval_id for update;
 if not found or a.status not in ('PENDING','APPROVED') then
 return jsonb_build_object('ok',false,'reason','Request is no longer cancellable.'); end if;
 update public.approvals set status='CANCELLED',reviewed_by=p_reviewer,reviewed_at=clock_timestamp() where id=a.id;
 insert into public.audit_events(identity,action,decision,reason,approval_id,metadata)
 values(p_reviewer,'cancel_approval','CANCELLED','Human administrator cancelled the request.',a.id,
 jsonb_build_object('previous_status',a.status,'actor_type','human'));
 return jsonb_build_object('ok',true,'approval_id',a.id,'status','CANCELLED');
end $$;
revoke all on function public.cancel_approval(text,text) from public,anon,authenticated;
grant execute on function public.cancel_approval(text,text) to service_role;
commit;

