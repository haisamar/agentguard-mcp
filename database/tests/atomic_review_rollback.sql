begin;
create function pg_temp.fail_review_audit() returns trigger language plpgsql as $$ begin raise exception 'intentional review audit failure'; end $$;
create trigger review_audit_rollback_verify before insert on public.audit_events for each row when (new.approval_id like 'apr_review_rollback_%') execute function pg_temp.fail_review_audit();
do $$ declare rid text := 'apr_review_rollback_' || replace(gen_random_uuid()::text,'-',''); failed boolean:=false; s text; n integer;
begin
insert into public.approvals(id,requesting_identity,action,payload) values(rid,'test-fixture:not-human','issue_refund','{"account_id":"acct_001","amount":751}');
begin perform public.review_approval(rid,'human:test-fixture:not-human','APPROVED');
exception when others then
 if sqlerrm <> 'intentional review audit failure' then raise; end if;
 failed:=true;
end;
assert failed;
select status into s from public.approvals where id=rid;
assert s='PENDING';
select count(*) into n from public.audit_events where approval_id=rid;
assert n=0;
end $$;
rollback;
