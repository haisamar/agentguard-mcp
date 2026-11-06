begin;
do $$
declare rid text := 'apr_binding_verify_' || replace(gen_random_uuid()::text,'-','');
 blocked boolean; r jsonb; n integer;
begin
 insert into public.approvals(id,requesting_identity,action,payload)
 values(rid,'test-fixture:not-human','issue_refund','{"account_id":"acct_001","amount":751,"reason":"binding verification"}');
 -- Pending requests cannot be changed behind an open approval card.
 blocked:=false;
 begin update public.approvals set payload=jsonb_set(payload,'{amount}','1') where id=rid;
 exception when check_violation then blocked:=true; end;
 assert blocked, 'Pending payload mutation was accepted';
 r:=public.review_approval(rid,'human:test-fixture:not-human','APPROVED');
 assert r->>'ok'='true';
 blocked:=false;
 begin update public.approvals set requesting_identity='other-agent' where id=rid;
 exception when check_violation then blocked:=true; end;
 assert blocked, 'Requester mutation was accepted';
 blocked:=false;
 begin update public.approvals set payload=jsonb_set(payload,'{account_id}','"acct_002"') where id=rid;
 exception when check_violation then blocked:=true; end;
 assert blocked, 'Recipient mutation was accepted';
 blocked:=false;
 begin update public.approvals set action='different_action' where id=rid;
 exception when check_violation then blocked:=true; end;
 assert blocked, 'Action mutation was accepted';
 blocked:=false;
 begin update public.approvals set created_at=clock_timestamp() where id=rid;
 exception when check_violation then blocked:=true; end;
 assert blocked, 'Expiry extension was accepted';
 r:=public.execute_refund_with_receipt(rid,'test-fixture:not-human');
 assert r->>'decision'='ALLOW';
 assert (r->>'amount_minor')::bigint=75100;
 select count(*) into n from public.refund_receipts where approval_id=rid and account_id='acct_001' and amount_minor=75100;
 assert n=1;
 r:=public.execute_refund_with_receipt(rid,'test-fixture:not-human');
 assert r->>'decision'='DENY';
 select count(*) into n from public.refund_receipts where approval_id=rid;
 assert n=1;
end $$;
rollback;

