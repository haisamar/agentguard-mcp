create function public.autonomous_budget_status() returns jsonb
language sql stable security invoker set search_path='' as $$
select jsonb_build_object(
 'limit_minor',50000,'spent_minor',coalesce(sum(amount_minor),0),
 'remaining_minor',greatest(0,50000-coalesce(sum(amount_minor),0)),
 'currency','USD','window_hours',24,'as_of',now())
from public.autonomous_refund_receipts
where created_at > now()-interval '24 hours';
$$;
revoke all on function public.autonomous_budget_status() from public,anon,authenticated;
grant execute on function public.autonomous_budget_status() to service_role;
