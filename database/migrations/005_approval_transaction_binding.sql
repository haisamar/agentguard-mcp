begin;
-- Freeze the requested transaction from creation onward. Review/status fields
-- may change, but changing the transaction requires a new approval request.
create function public.protect_approval_transaction() returns trigger
language plpgsql set search_path='' as $$
begin
 if new.id is distinct from old.id
 or new.requesting_identity is distinct from old.requesting_identity
 or new.action is distinct from old.action
 or new.payload is distinct from old.payload
 or new.created_at is distinct from old.created_at then
   raise exception 'Approval transaction is immutable; submit a new request.'
     using errcode='23514';
 end if;
 return new;
end $$;
revoke all on function public.protect_approval_transaction() from public,anon,authenticated;
create trigger approval_transaction_immutable before update on public.approvals
for each row execute function public.protect_approval_transaction();
commit;
