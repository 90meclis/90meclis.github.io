-- 2026-10-20c: yerel lig izi — teams.domestic_league (tekrar çalıştırılabilir)
alter table teams add column if not exists domestic_league text;
create index if not exists teams_domestic_league_idx on teams (domestic_league);
