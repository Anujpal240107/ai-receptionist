-- Native Python/Streamlit integration; additive and repeatable.
begin;
create table if not exists public.reception_schema(version integer primary key, applied_at timestamptz not null default now());
create table if not exists public.reception_restaurants(id uuid primary key,name text not null);
insert into public.reception_restaurants values('d9f3d667-08c5-41bc-bd38-c326ea392e09','Ugly SaaS Restaurant') on conflict do nothing;
create table if not exists public.reception_menu(restaurant uuid references public.reception_restaurants,sku text,name text not null,price integer not null check(price>0),primary key(restaurant,sku));
insert into public.reception_menu values
 ('d9f3d667-08c5-41bc-bd38-c326ea392e09','pizza','Pizza',200),
 ('d9f3d667-08c5-41bc-bd38-c326ea392e09','burger','Burger',150),
 ('d9f3d667-08c5-41bc-bd38-c326ea392e09','pasta','Pasta',180),
 ('d9f3d667-08c5-41bc-bd38-c326ea392e09','cold-drink','Cold Drink',50) on conflict do nothing;
-- Membership cannot be self-granted. Only a database administrator can appoint staff.
create table if not exists public.reception_staff(restaurant uuid references public.reception_restaurants,member uuid references auth.users on delete cascade,primary key(restaurant,member));
create table if not exists public.reception_conversations(
 id uuid primary key default gen_random_uuid(),owner uuid not null references auth.users on delete cascade,
 restaurant uuid not null references public.reception_restaurants,created_at timestamptz not null default now(),pending uuid,pending_at timestamptz,unique(id,owner,restaurant));
create table if not exists public.reception_messages(
 id bigint generated always as identity primary key,conversation uuid not null,owner uuid not null,restaurant uuid not null,
 role text not null check(role in ('user','assistant')),content text not null check(length(content) between 1 and 2000),created_at timestamptz not null default now(),
 foreign key(conversation,owner,restaurant) references public.reception_conversations(id,owner,restaurant) on delete cascade);
create index if not exists reception_message_lookup on public.reception_messages(conversation,id);
create table if not exists public.reception_orders(
 id uuid primary key default gen_random_uuid(),owner uuid not null references auth.users on delete cascade,restaurant uuid not null references public.reception_restaurants,
 request_id uuid not null,conversation uuid not null,customer_name text not null check(length(btrim(customer_name)) between 1 and 120),
 phone text not null check(phone ~ '^\+?[0-9 ()-]{7,25}$'),address text not null check(length(btrim(address)) between 10 and 600),
 payment_preference text not null check(payment_preference in ('Cash on Delivery','Online Payment')),
 payment_status text not null default 'unpaid' check(payment_status='unpaid'),total integer not null check(total between 1 and 1000000),
 status text not null default 'placed' check(status in ('placed','accepted','completed','cancelled')),created_at timestamptz not null default now(),
 unique(owner,request_id),unique(id,owner),foreign key(conversation,owner,restaurant) references public.reception_conversations(id,owner,restaurant) on delete cascade);
create table if not exists public.reception_order_items(
 order_id uuid references public.reception_orders on delete cascade,restaurant uuid not null,sku text not null,
 quantity integer not null check(quantity between 1 and 20),unit_price integer not null check(unit_price>0),primary key(order_id,sku),
 foreign key(restaurant,sku) references public.reception_menu(restaurant,sku));
-- Small private order attachments are included in the encrypted database recovery.
create table if not exists public.reception_files(
 id uuid primary key default gen_random_uuid(),order_id uuid not null,owner uuid not null,
 name text not null check(length(name) between 1 and 100 and name !~ '[/\\\r\n]'),
 media_type text not null check(media_type in ('text/plain','application/pdf','image/png','image/jpeg')),
 body bytea not null check(octet_length(body) between 1 and 262144),created_at timestamptz not null default now(),
 foreign key(order_id,owner) references public.reception_orders(id,owner) on delete cascade);
create table if not exists public.reception_budgets(owner uuid references auth.users on delete cascade,action text not null,bucket timestamptz not null,count integer not null check(count>0),primary key(owner,action,bucket));
create table if not exists public.reception_events(id bigint generated always as identity primary key,actor uuid references auth.users on delete cascade,
 category text not null check(category in ('conversation_created','order_placed','order_status','file_added','data_deleted','provider_failed')),created_at timestamptz not null default now());

create or replace function public.reception_uid() returns uuid language sql stable security definer set search_path='' as $$
 select s.user_id from auth.sessions s where s.user_id=auth.uid() and s.id::text=auth.jwt()->>'session_id'
 and (auth.jwt()->>'exp')::bigint>extract(epoch from now()) limit 1
$$;
revoke all on function public.reception_uid() from public,anon;
grant execute on function public.reception_uid() to authenticated;
create or replace function public.reception_is_staff(r uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.reception_staff where restaurant=r and member=public.reception_uid())
$$;
revoke all on function public.reception_is_staff(uuid) from public,anon;
grant execute on function public.reception_is_staff(uuid) to authenticated;
do $migration$ declare t text; begin
 foreach t in array array['reception_schema','reception_restaurants','reception_menu','reception_staff','reception_conversations','reception_messages','reception_orders','reception_order_items','reception_files','reception_budgets','reception_events'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from public,anon,authenticated',t);
 end loop;
end $migration$;
grant select on public.reception_restaurants,public.reception_menu,public.reception_conversations,public.reception_messages,public.reception_orders,public.reception_order_items,public.reception_files to authenticated;
drop policy if exists reception_read on public.reception_restaurants;
create policy reception_read on public.reception_restaurants for select to authenticated using(public.reception_uid() is not null);
drop policy if exists reception_read on public.reception_menu;
create policy reception_read on public.reception_menu for select to authenticated using(public.reception_uid() is not null);
drop policy if exists reception_read on public.reception_conversations;
create policy reception_read on public.reception_conversations for select to authenticated using(owner=public.reception_uid());
drop policy if exists reception_read on public.reception_messages;
create policy reception_read on public.reception_messages for select to authenticated using(owner=public.reception_uid());
drop policy if exists reception_read on public.reception_orders;
create policy reception_read on public.reception_orders for select to authenticated using(owner=public.reception_uid() or public.reception_is_staff(restaurant));
drop policy if exists reception_read on public.reception_order_items;
create policy reception_read on public.reception_order_items for select to authenticated using(exists(select 1 from public.reception_orders o where o.id=order_id));
drop policy if exists reception_read on public.reception_files;
create policy reception_read on public.reception_files for select to authenticated using(owner=public.reception_uid());

create or replace function public.reception_keys(p jsonb,allowed text[]) returns void language plpgsql set search_path='' as $$
begin
 if jsonb_typeof(p) is distinct from 'object' or exists(select 1 from jsonb_object_keys(p) k where not k=any(allowed)) then raise exception 'Unexpected input fields' using errcode='22023';end if;
end $$;
revoke all on function public.reception_keys(jsonb,text[]) from public,anon,authenticated;
create or replace function public.reception_budget(u uuid,a text,minute_max integer,day_max integer) returns void language plpgsql security definer set search_path='' as $$
declare b timestamptz; n integer; granularity text;
begin
 perform pg_advisory_xact_lock(hashtextextended(u::text,21));
 foreach granularity in array array['minute','day'] loop
  b:=date_trunc(granularity,now());
  insert into public.reception_budgets values(u,a||':'||granularity,b,1)
  on conflict(owner,action,bucket) do update set count=reception_budgets.count+1 returning count into n;
  if n>(case when granularity='day' then day_max else minute_max end) then raise exception 'Usage allowance reached' using errcode='P0001';end if;
 end loop;
end $$;
revoke all on function public.reception_budget(uuid,text,integer,integer) from public,anon,authenticated;

create or replace function public.reception_service(action text,payload jsonb default '{}'::jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
#variable_conflict use_column
declare u uuid:=public.reception_uid(); r constant uuid:='d9f3d667-08c5-41bc-bd38-c326ea392e09';
 c public.reception_conversations; o public.reception_orders; f public.reception_files;
 item jsonb; menu public.reception_menu; total_price integer:=0; qty integer; rid uuid; bytes bytea; expected text;
begin
 if u is null then raise exception 'Sign in again' using errcode='28000';end if;
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>360000 then raise exception 'Invalid request size' using errcode='22023';end if;
 perform pg_advisory_xact_lock(hashtextextended(u::text,21));
 if action='bootstrap' then
  perform public.reception_keys(payload,'{}');return jsonb_build_object('user',u,'restaurant',r,'operator',public.reception_is_staff(r),'menu',(select jsonb_agg(to_jsonb(m) order by sku) from public.reception_menu m where restaurant=r));
 elsif action='conversations' then
  perform public.reception_keys(payload,'{}');return coalesce((select jsonb_agg(to_jsonb(t) order by created_at desc) from (select id,created_at from public.reception_conversations where owner=u order by created_at desc limit 30)t),'[]');
 elsif action='new_conversation' then
  perform public.reception_keys(payload,'{}');perform public.reception_budget(u,'conversation',3,30);
  if (select count(*) from public.reception_conversations where owner=u)>=30 then raise exception 'Delete an old conversation first';end if;
  insert into public.reception_conversations(owner,restaurant) values(u,r) returning * into c;
  insert into public.reception_events(actor,category) values(u,'conversation_created');return to_jsonb(c)-'owner'-'pending';
 elsif action in ('messages','chat_start','chat_finish','reset') then
  perform public.reception_keys(payload,array['conversation','content','request_id']);
  select * into c from public.reception_conversations where id=(payload->>'conversation')::uuid and owner=u for update;
  if c.id is null then raise exception 'Conversation not found' using errcode='42501';end if;
  if action='messages' then
   return coalesce((select jsonb_agg(to_jsonb(t) order by id) from (select id,role,content from public.reception_messages where conversation=c.id order by id)t),'[]');
  elsif action='reset' then
   perform public.reception_budget(u,'mutation',30,300);delete from public.reception_messages where conversation=c.id;
   update public.reception_conversations set pending=null,pending_at=null where id=c.id;return '{"ok":true}';
  elsif action='chat_start' then
   if jsonb_typeof(payload->'content') is distinct from 'string' or length(btrim(payload->>'content')) not between 1 and 2000 then raise exception 'Message must contain 1 to 2000 characters' using errcode='22023';end if;
   if c.pending is not null and c.pending_at>now()-interval '60 seconds' then raise exception 'A reply is still in progress';end if;
   perform public.reception_budget(u,'chat',10,100);
   if (select count(*) from public.reception_messages where conversation=c.id)>=200 then raise exception 'Start a new conversation';end if;
   rid:=gen_random_uuid();insert into public.reception_messages(conversation,owner,restaurant,role,content) values(c.id,u,r,'user',payload->>'content');
   update public.reception_conversations set pending=rid,pending_at=now() where id=c.id;
   return jsonb_build_object('request_id',rid,'messages',(select jsonb_agg(to_jsonb(t) order by id) from (select id,role,content from public.reception_messages where conversation=c.id order by id desc limit 20)t));
  else
   if c.pending is null or c.pending is distinct from (payload->>'request_id')::uuid then raise exception 'Reply is no longer current';end if;
   if jsonb_typeof(payload->'content') is distinct from 'string' or length(btrim(payload->>'content')) not between 1 and 2000 then raise exception 'Invalid reply' using errcode='22023';end if;
   insert into public.reception_messages(conversation,owner,restaurant,role,content) values(c.id,u,r,'assistant',payload->>'content');
   update public.reception_conversations set pending=null,pending_at=null where id=c.id;return '{"ok":true}';
  end if;
 elsif action='place_order' then
  perform public.reception_keys(payload,array['request_id','conversation','customer_name','phone','address','payment_preference','items']);
  perform pg_advisory_xact_lock(hashtextextended(u::text,21));select * into o from public.reception_orders where owner=u and request_id=(payload->>'request_id')::uuid;
  if o.id is not null then return to_jsonb(o);end if;
  perform public.reception_budget(u,'order',5,30);
  if jsonb_typeof(payload->'items') is distinct from 'array' or jsonb_array_length(payload->'items') not between 1 and 4 then raise exception 'Choose one to four menu items' using errcode='22023';end if;
  if exists(select 1 from jsonb_array_elements(payload->'items') v group by v->>'sku' having count(*)>1) then raise exception 'Duplicate menu item' using errcode='22023';end if;
  for item in select * from jsonb_array_elements(payload->'items') loop
   perform public.reception_keys(item,array['sku','quantity']);
   if jsonb_typeof(item->'quantity') is distinct from 'number' or (item->>'quantity')!~'^[0-9]{1,2}$' then raise exception 'Invalid quantity' using errcode='22023';end if;
   qty:=(item->>'quantity')::integer;select * into menu from public.reception_menu where restaurant=r and sku=item->>'sku';
   if menu.sku is null or qty not between 1 and 20 then raise exception 'Invalid menu selection' using errcode='22023';end if;
   total_price:=total_price+menu.price*qty;
  end loop;
  foreach expected in array array['customer_name','phone','address','payment_preference'] loop
   if jsonb_typeof(payload->expected) is distinct from 'string' then raise exception 'Missing order details' using errcode='22023';end if;
  end loop;
  insert into public.reception_orders(owner,restaurant,request_id,conversation,customer_name,phone,address,payment_preference,total)
  values(u,r,(payload->>'request_id')::uuid,(payload->>'conversation')::uuid,payload->>'customer_name',payload->>'phone',payload->>'address',payload->>'payment_preference',total_price) returning * into o;
  for item in select * from jsonb_array_elements(payload->'items') loop
   insert into public.reception_order_items select o.id,r,sku,(item->>'quantity')::integer,price from public.reception_menu where restaurant=r and sku=item->>'sku';
  end loop;
  insert into public.reception_events(actor,category) values(u,'order_placed');return to_jsonb(o);
 elsif action in ('orders','operator_orders') then
  perform public.reception_keys(payload,'{}');if action='operator_orders' and not public.reception_is_staff(r) then raise exception 'Restaurant operator required' using errcode='42501';end if;
  return coalesce((select jsonb_agg(to_jsonb(t) order by created_at desc) from (select o.*,
   coalesce((select jsonb_agg(to_jsonb(i)) from public.reception_order_items i where i.order_id=o.id),'[]') items
   from public.reception_orders o where (o.owner=u or action='operator_orders') and o.restaurant=r order by created_at desc limit 100)t),'[]');
 elsif action='order_status' then
  perform public.reception_keys(payload,array['order_id','status']);if not public.reception_is_staff(r) then raise exception 'Restaurant operator required' using errcode='42501';end if;
  perform public.reception_budget(u,'mutation',30,300);select * into o from public.reception_orders where id=(payload->>'order_id')::uuid and restaurant=r for update;
  if o.id is null or not ((o.status='placed' and payload->>'status' in ('accepted','cancelled')) or (o.status='accepted' and payload->>'status' in ('completed','cancelled'))) then raise exception 'Invalid order transition' using errcode='22023';end if;
  update public.reception_orders set status=payload->>'status' where id=o.id;insert into public.reception_events(actor,category) values(u,'order_status');return '{"ok":true}';
 elsif action in ('files','add_file','download_file','delete_file') then
  perform public.reception_keys(payload,array['order_id','file_id','name','media_type','base64']);
  if action in ('download_file','delete_file') then
   select * into f from public.reception_files where id=(payload->>'file_id')::uuid and owner=u;if f.id is null then raise exception 'File not found' using errcode='42501';end if;
   if action='download_file' then return jsonb_build_object('name',f.name,'media_type',f.media_type,'base64',encode(f.body,'base64'));end if;
   perform public.reception_budget(u,'mutation',30,300);delete from public.reception_files where id=f.id;return '{"ok":true}';
  end if;
  select * into o from public.reception_orders where id=(payload->>'order_id')::uuid and owner=u;if o.id is null then raise exception 'Order not found' using errcode='42501';end if;
  if action='files' then return coalesce((select jsonb_agg(jsonb_build_object('id',id,'name',name,'media_type',media_type,'bytes',octet_length(body))) from public.reception_files where order_id=o.id and owner=u),'[]');end if;
  perform public.reception_budget(u,'file',10,50);bytes:=decode(payload->>'base64','base64');
  if (select count(*) from public.reception_files where order_id=o.id)>=10 or coalesce((select sum(octet_length(body)) from public.reception_files where owner=u),0)+octet_length(bytes)>5242880 then raise exception 'Private file allowance reached';end if;
  insert into public.reception_files(order_id,owner,name,media_type,body) values(o.id,u,payload->>'name',payload->>'media_type',bytes) returning * into f;
  insert into public.reception_events(actor,category) values(u,'file_added');return jsonb_build_object('id',f.id,'name',f.name);
 elsif action='export' then
  perform public.reception_keys(payload,'{}');return jsonb_build_object('version',1,'exported_at',now(),
   'conversations',coalesce((select jsonb_agg(to_jsonb(c)-'pending') from public.reception_conversations c where owner=u),'[]'),
   'messages',coalesce((select jsonb_agg(to_jsonb(m)) from public.reception_messages m where owner=u),'[]'),
   'orders',coalesce((select jsonb_agg(to_jsonb(o)) from public.reception_orders o where owner=u),'[]'),
   'items',coalesce((select jsonb_agg(to_jsonb(i)) from public.reception_order_items i join public.reception_orders o on o.id=i.order_id where o.owner=u),'[]'),
   'files',coalesce((select jsonb_agg(jsonb_build_object('id',id,'order_id',order_id,'name',name,'media_type',media_type,'base64',encode(body,'base64'))) from public.reception_files where owner=u),'[]'));
 elsif action='delete_data' then
  perform public.reception_keys(payload,array['confirm']);if payload->>'confirm' is distinct from 'DELETE MY RECEPTIONIST DATA' then raise exception 'Confirm deletion' using errcode='22023';end if;
  perform public.reception_budget(u,'delete',1,3);delete from public.reception_conversations where owner=u;delete from public.reception_events where actor=u;
  insert into public.reception_events(actor,category) values(u,'data_deleted');return '{"ok":true}';
 elsif action='provider_failure' then
  perform public.reception_keys(payload,'{}');perform public.reception_budget(u,'event',5,100);insert into public.reception_events(actor,category) values(u,'provider_failed');return '{"ok":true}';
 else raise exception 'Unknown service action' using errcode='22023';end if;
end $$;
revoke all on function public.reception_service(text,jsonb) from public,anon;
grant execute on function public.reception_service(text,jsonb) to authenticated;
create or replace function public.reception_retention() returns jsonb language plpgsql security definer set search_path='' as $$
declare n integer;begin
 delete from public.reception_conversations where created_at<now()-interval '90 days';get diagnostics n=row_count;
 delete from public.reception_budgets where bucket<now()-interval '2 days';delete from public.reception_events where created_at<now()-interval '30 days';
 return jsonb_build_object('expired_conversations',n);
end $$;
revoke all on function public.reception_retention() from public,anon,authenticated;
insert into public.reception_schema(version) values(1) on conflict do nothing;
commit;

