-- 2026-10-20f: geri testte canlı kuralın (w = max(0.20, w*)) ölçüleri. Tekrar çalıştırılabilir.
alter table model_backtest add column if not exists w_live numeric;
alter table model_backtest add column if not exists ll_live numeric;
alter table model_backtest add column if not exists brier_live numeric;
create or replace view v_model_backtest with (security_invoker = true) as
  select market, segment, n, label, brier_model, brier_market, brier_blend, ll_model, ll_market, ll_blend,
         w_opt as harman_agirligi, n_value as deger_secim_sayisi, hit_value as deger_isabet, roi_value as deger_roi,
         calib as kalibrasyon, leagues, model_version, computed_at, w_live as canli_agirlik, ll_live as ll_canli,
         brier_live as brier_canli
  from model_backtest;
grant select on v_model_backtest to anon, authenticated;
