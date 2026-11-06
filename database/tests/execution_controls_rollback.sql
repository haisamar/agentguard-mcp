begin;
create function pg_temp.fail_control_audit() returns trigger language plpgsql as $$
begin raise exception 'intentional control audit failure'; end $$;
create trigger control_audit_rollback_verify before insert on public.audit_events
for each row when(new.identity like 'human:test-control-rollback:%' and new.action in ('cancel_approval','set_execution_pause'))
execute function pg_temp.fail_control_audit();
do $$
declare who text:='human:test-control-rollback:'||gen_random_uuid(); rid text; r jsonb;
failed boolean; s text; paused_value boolean;
begin
 select paused into paused_value from public.execution_control where id=1;
 assert paused_value=false,'Requires execution initially enabled';
 r:=public.submit_refund_request(who,'test_cancel','acct_001',75100,'USD','Synthetic rollback');
 rid:=r->>'approval_id';
 r:=public.review_approval(rid,'human:test-fixture:not-human','APPROVED');
 assert r->>'ok'='true';
 failed:=false;
 begin perform public.set_execution_pause(true,who);
 exception when others then
 if sqlerrm<>'intentional control audit failure' then raise; end if;
 failed:=true;
 end;
 assert failed;
 select paused into paused_value from public.execution_control where id=1;
 assert paused_value=false,'Partial pause remained after audit failure';
 failed:=false;
 begin perform public.cancel_approval(rid,who);
 exception when others then
 if sqlerrm<>'intentional control audit failure' then raise; end if;
 failed:=true;
 end;
 assert failed;
 select status into s from public.approvals where id=rid;
 assert s='APPROVED','Partial cancellation remained after audit failure';
end $$;
rollback;
