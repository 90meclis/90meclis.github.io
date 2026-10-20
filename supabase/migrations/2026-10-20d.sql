-- 2026-10-20d: geri test (model_backtest + v_model_backtest; canlı kilitli kayıttan AYRI) ve kilitli seçimde
-- kalibrasyon parametreleri (predictions.calibration, bot_picks.calibration). Tekrar çalıştırılabilir.
create table if not exists model_backtest (
  market text not null, segment text not null default 'tum', n int,
  brier_model numeric, brier_market numeric, brier_blend numeric,
  ll_model numeric, ll_market numeric, ll_blend numeric, w_opt numeric,
  n_value int, hit_value numeric, roi_value numeric, calib jsonb, computed_at timestamptz,
  label text not null default 'backtest', model_version text, leagues jsonb,
  primary key (market, segment));
alter table model_backtest enable row level security;
drop policy if exists herkes_okur on model_backtest;
create policy herkes_okur on model_backtest for select using (true);
grant select on model_backtest to anon, authenticated;
alter table predictions add column if not exists calibration jsonb;
alter table bot_picks add column if not exists calibration jsonb;
create or replace view v_model_backtest with (security_invoker = true) as
  select market, segment, n, label, brier_model, brier_market, brier_blend, ll_model, ll_market, ll_blend,
         w_opt as harman_agirligi, n_value as deger_secim_sayisi, hit_value as deger_isabet, roi_value as deger_roi,
         calib as kalibrasyon, leagues, model_version, computed_at
  from model_backtest;
grant select on v_model_backtest to anon, authenticated;
