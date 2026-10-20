-- 2026-10-20b: Avrupa izi — maç bazlı istatistik görünümüne aşama (Ön eleme/play-off | Lig aşaması | Eleme turları)
-- ve Avrupa kupalarında lig aşaması puan durumu. Yalnızca görünüm; tekrar çalıştırılabilir.
create or replace view v_takim_mac_istatistik with (security_invoker = true) as
  with m as (
    select m.*, case when m.league in ('CL','EL','ECL') then 'Avrupa' else 'Lig' end as competition,
           case when extract(month from now()) >= 7 then make_date(extract(year from now())::int, 7, 1)
                else make_date(extract(year from now())::int - 1, 7, 1) end as s0
    from matches m where m.status = 'bitti' and m.home_goals is not null
  )
  select m.id as match_id, m.kickoff_at, m.league, m.competition, t.side,
         case when t.side = 'home' then 'İç saha' else 'Deplasman' end as venue,
         case when t.side = 'home' then m.home_team_id else m.away_team_id end as team_id,
         split_part(case when t.side = 'home' then m.home_team_id else m.away_team_id end, ':', 2) as team_slug,
         case when t.side = 'home' then m.home_name else m.away_name end as team_name,
         case when t.side = 'home' then m.away_name else m.home_name end as opponent,
         case when t.side = 'home' then m.home_goals else m.away_goals end as goals_for,
         case when t.side = 'home' then m.away_goals else m.home_goals end as goals_against,
         case when t.side = 'home' then m.ht_home_goals else m.ht_away_goals end as ht_for,
         case when t.side = 'home' then m.ht_away_goals else m.ht_home_goals end as ht_against,
         (m.home_goals > 0 and m.away_goals > 0) as btts,
         me.corners as corners_for, op.corners as corners_against,
         (me.yellow + coalesce(me.red, 0)) as cards_for, (op.yellow + coalesce(op.red, 0)) as cards_against,
         me.shots as shots_for, op.shots as shots_against,
         me.shots_on_target as sot_for, op.shots_on_target as sot_against,
         me.goal_kicks as goal_kicks_for, op.goal_kicks as goal_kicks_against,
         me.fouls as fouls_for, op.fouls as fouls_against, me.xg as xg_for, op.xg as xg_against,
         me.possession as possession, m.referee,
         case when m.competition = 'Lig' then 'Lig'
              when m.kickoff_at < make_date(extract(year from m.s0)::int, 9, 1) then 'Ön eleme/play-off'
              when m.kickoff_at < make_date(extract(year from m.s0)::int + 1, 2, 1) then 'Lig aşaması'
              else 'Eleme turları' end as asama
  from m
  cross join (values ('home'), ('away')) t(side)
  left join match_stats me on me.match_id = m.id and me.side = t.side
  left join match_stats op on op.match_id = m.id and op.side = case when t.side = 'home' then 'away' else 'home' end
  where m.kickoff_at >= m.s0;


create or replace view v_avrupa_puan_durumu with (security_invoker = true) as
  select league, team_slug, max(team_name) as team_name, count(*) as o,
         count(*) filter (where goals_for > goals_against) as g, count(*) filter (where goals_for = goals_against) as b,
         count(*) filter (where goals_for < goals_against) as m, sum(goals_for) as ag, sum(goals_against) as yg,
         sum(goals_for) - sum(goals_against) as av,
         3 * count(*) filter (where goals_for > goals_against) + count(*) filter (where goals_for = goals_against) as puan,
         rank() over (partition by league order by
           3 * count(*) filter (where goals_for > goals_against) + count(*) filter (where goals_for = goals_against) desc,
           sum(goals_for) - sum(goals_against) desc, sum(goals_for) desc) as sira
  from v_takim_mac_istatistik where competition = 'Avrupa' and asama = 'Lig aşaması'
  group by league, team_slug;

grant select on v_takim_mac_istatistik, v_avrupa_puan_durumu to anon, authenticated;
