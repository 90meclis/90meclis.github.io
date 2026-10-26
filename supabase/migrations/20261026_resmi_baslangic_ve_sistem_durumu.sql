-- 27.10.2026 resmî kayıt başlangıcı: deneme dönemi kayıtları deneme_yedek_* tablolarına taşındı (uygulandı)
begin;
create table if not exists deneme_yedek_predictions (like predictions including all);
create table if not exists deneme_yedek_coupons (like coupons including all);
create table if not exists deneme_yedek_bot_picks (like bot_picks including all);
create table if not exists deneme_yedek_kanit_muhru as select * from kanit_muhru where false;
alter table deneme_yedek_predictions add column if not exists yedeklendi_at timestamptz default now();
alter table deneme_yedek_coupons add column if not exists yedeklendi_at timestamptz default now();
alter table deneme_yedek_bot_picks add column if not exists yedeklendi_at timestamptz default now();
alter table deneme_yedek_kanit_muhru add column if not exists yedeklendi_at timestamptz default now();
insert into deneme_yedek_predictions select p.* from predictions p where p.kickoff_at < '2026-10-26T21:00:00Z' or p.coupon_id in (select id from coupons where first_kickoff_at < '2026-10-26T21:00:00Z') on conflict do nothing;
insert into deneme_yedek_coupons select c.* from coupons c where c.first_kickoff_at < '2026-10-26T21:00:00Z' on conflict do nothing;
insert into deneme_yedek_bot_picks select b.* from bot_picks b where b.kickoff_at < '2026-10-26T21:00:00Z' on conflict do nothing;
insert into deneme_yedek_kanit_muhru select m.* from kanit_muhru m where m.muhurlendi_at < '2026-10-26T21:00:00Z';
alter table predictions disable trigger user;
alter table coupons disable trigger user;
alter table bot_picks disable trigger user;
alter table kanit_muhru disable trigger user;
delete from predictions where id in (select id from deneme_yedek_predictions);
delete from coupons where id in (select id from deneme_yedek_coupons);
delete from bot_picks where id in (select id from deneme_yedek_bot_picks);
delete from kanit_muhru where muhurlendi_at < '2026-10-26T21:00:00Z';
alter table predictions enable trigger user;
alter table coupons enable trigger user;
alter table bot_picks enable trigger user;
alter table kanit_muhru enable trigger user;
alter table deneme_yedek_predictions enable row level security;
alter table deneme_yedek_coupons enable row level security;
alter table deneme_yedek_bot_picks enable row level security;
alter table deneme_yedek_kanit_muhru enable row level security;
commit;
select (select count(*) from predictions) p,(select count(*) from coupons) c,(select count(*) from bot_picks) b,(select count(*) from kanit_muhru) m,
 (select count(*) from deneme_yedek_predictions) yp,(select count(*) from deneme_yedek_coupons) yc,(select count(*) from deneme_yedek_bot_picks) yb,(select count(*) from deneme_yedek_kanit_muhru) ym;

-- Sistem sağlığı görünümü
create or replace view v_sistem_durumu as
with is_ as (
  select * from (values ('yayin', 3), ('sonuclandir', 6), ('gundem', 12), ('gecmis', 30)) v(is_adi, beklenen_saat)
)
select i.is_adi, i.beklenen_saat,
  (select s.updated_at from source_status s where s.source = 'is:' || i.is_adi) as son_calisma,
  (select s.ok from source_status s where s.source = 'is:' || i.is_adi) as son_ok,
  (select s.message from source_status s where s.source = 'is:' || i.is_adi) as son_mesaj,
  greatest((select max(s.updated_at) from source_status s where s.source like 'is:' || i.is_adi || ':%' and s.ok), (select s.updated_at from source_status s where s.source = 'adim:' || i.is_adi)) as son_basari,
  coalesce(greatest((select max(s.updated_at) from source_status s where s.source like 'is:' || i.is_adi || ':%' and s.ok), (select s.updated_at from source_status s where s.source = 'adim:' || i.is_adi))
           < now() - make_interval(hours => i.beklenen_saat), true) as gecikti
from is_ i;
grant select on v_sistem_durumu to anon, authenticated;
