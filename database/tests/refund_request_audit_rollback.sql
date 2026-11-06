begin;
create function pg_temp.fail_request_audit() returns trigger language plpgsql as $$
begin raise exception 'intentional request audit failure'; end $$;
create trigger request_audit_rollback_verify before insert on public.audit_events
for each row when (new.identity like 'test-request-rollback:%')
execute function pg_temp.fail_request_audit();
do $$
declare who text := 'test-request-rollback:'||gen_random_uuid(); amount bigint;
failed boolean; n integer;
begin
 assert (public.autonomous_budget_status()->>'remaining_minor')::bigint>=1;
 foreach amount in array array[1::bigint,75100::bigint] loop
  failed:=false;
  begin
   perform public.submit_refund_request(who,'rollback_'||amount,'acct_001',amount,'USD','Synthetic rollback test');
  exception when others then
   if sqlerrm <> 'intentional request audit failure' then raise; end if;
   failed:=true;
  end;
  assert failed, 'Expected audit failure was not raised';
  select count(*) into n from public.refund_requests where identity=who;
  assert n=0, 'Partial idempotency record remained';
  select count(*) into n from public.autonomous_refund_receipts where identity=who;
  assert n=0, 'Partial refund receipt remained';
  select count(*) into n from public.approvals where requesting_identity=who;
  assert n=0, 'Partial pending approval remained';
  select count(*) into n from public.audit_events where identity=who;
  assert n=0, 'Partial audit remained';
 end loop;
end $$;
rollback;

