begin;
do $$
declare
  requester text := 'synthetic-expiry-test';
  expired text := 'apr_expired_' || gen_random_uuid();
  future_time text := 'apr_future_' || gen_random_uuid();
  approved text := 'apr_approved_expired_' || gen_random_uuid();
  payload jsonb := '{"account_id":"acct_001","amount":755,"reason":"Synthetic expiry test"}';
  reviewer text := 'human:synthetic-expiry-test';
  result jsonb;
begin
  insert into public.approvals(id,requesting_identity,action,payload,created_at)
    values (expired,requester,'issue_refund',payload,clock_timestamp()-interval '61 minutes'),
           (future_time,requester,'issue_refund',payload,clock_timestamp()+interval '1 minute');
  result := public.review_approval(expired,reviewer,'APPROVED');
  assert result->>'ok' = 'false', 'Expired request approved';
  result := public.review_approval(future_time,reviewer,'APPROVED');
  assert result->>'ok' = 'false', 'Future-dated request approved';
  assert not exists (select 1 from public.audit_events where approval_id in (expired,future_time)), 'Rejected review created an audit of approval';
  insert into public.approvals(id,requesting_identity,action,payload,created_at,status,approved_by,approved_at)
    values (approved,requester,'issue_refund',payload,clock_timestamp()-interval '61 minutes','APPROVED',reviewer,clock_timestamp()-interval '60 minutes');
  result := public.execute_refund_with_receipt(approved,requester);
  assert result->>'decision' = 'DENY', 'Expired approval executed';
  assert not exists (select 1 from public.refund_receipts where approval_id=approved), 'Expired approval recorded a receipt';
end $$;
rollback;
