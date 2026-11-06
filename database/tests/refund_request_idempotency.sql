begin;
do $$
declare who text := 'test-idempotency-'||gen_random_uuid(); a jsonb; b jsonb; n integer;
begin
 a:=public.submit_refund_request(who,'req_one','acct_001',1,'USD','test');
 assert a->>'decision'='ALLOW', 'Requires at least one cent of available autonomous budget';
 b:=public.submit_refund_request(who,'req_one','acct_001',1,'USD','test');
 assert a=b;
 b:=public.submit_refund_request(who,'req_one','acct_002',1,'USD','test');
 assert b->>'decision'='DENY';
 b:=public.submit_refund_request(who,'req_one','acct_001',2,'USD','test');
 assert b->>'decision'='DENY';
 select count(*) into n from public.autonomous_refund_receipts where identity=who;
 assert n=1;
 a:=public.submit_refund_request(who,'req_high','acct_001',75100,'USD','test');
 b:=public.submit_refund_request(who,'req_high','acct_001',75100,'USD','test');
 assert a=b;
 select count(*) into n from public.approvals where requesting_identity=who;
 assert n=1;
 select count(*) into n from public.refund_requests where identity=who;
 assert n=2;
 assert not has_function_privilege('anon','public.submit_refund_request(text,text,text,bigint,text,text)','execute');
 assert not has_function_privilege('authenticated','public.submit_refund_request(text,text,text,bigint,text,text)','execute');
end $$;
rollback;

