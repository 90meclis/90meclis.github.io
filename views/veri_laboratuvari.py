import pandas as pd
import streamlit as st

from meclis import ui
from meclis.analysis import LeagueContext, season_start
from meclis.lab import market_tables
from meclis.timeutil import parse_dt

st.title("🧪 Veri Laboratuvarı")
st.caption("Pazar ligleri (takım tabloları) ve maç maç takım serileri — ortalamanın arkasındaki gerçek maçlar.")
ui.banner()
s, store, pool = ui.resources()
bot = ui.bot()

c1, c2, c3 = st.columns(3)
lg = c1.selectbox("Lig", s.leagues, format_func=ui.league_name)
scope = c2.radio("Kapsam", ["tümü", "iç saha", "deplasman"], horizontal=True)
last_n = c3.select_slider("Son kaç maç", options=[5, 10, 15, 20, 38, 76], value=10)
_ctx = bot.context(lg)
_s0 = season_start()
# Yalnızca bu sezon: kullanıcı isteği "geçmiş sezon değil bu sezon genelinde".
ctx = LeagueContext(_ctx.league, [m for m in _ctx.matches if parse_dt(m["kickoff_at"]) >= _s0], _ctx.stats)
if not ctx.matches:
    ui.empty_state("Bu lig için bu sezon henüz bitmiş maç yok.")
    st.stop()
st.caption(f"Bu sezon {len(ctx.matches)} bitmiş maç ({_s0:%d.%m.%Y} sonrası). İstatistikler birden çok kaynaktan birleştirilir; "
           "verisi olmayan pazarın tablosu gösterilmez.")

tables = market_tables(ctx, scope, last_n)
tabs = st.tabs(list(tables) + ["📉 Takım serisi (maç maç)", "🔥 Seriler"])
for tab, (name, df) in zip(tabs, tables.items()):
    with tab:
        st.dataframe(df, hide_index=True, width="stretch")

with tabs[len(tables)]:
    teams = sorted({(m["home_team_id"], m["home_name"]) for m in ctx.matches}, key=lambda x: x[1])
    tid = st.selectbox("Takım", [t[0] for t in teams], format_func=dict(teams).get)
    ser = pd.DataFrame(ctx.series(tid, last_n))
    if ser.empty:
        st.caption("Veri yok.")
    else:
        metric = st.selectbox("Grafikte göster", ["isabetli şut", "şut", "korner", "rakip korner", "kart", "rakip isabetli şut", "xG"])
        chart = ser[["tarih", "rakip", metric]].dropna()
        if not chart.empty:
            chart = chart.assign(maç=chart["tarih"] + " " + chart["rakip"]).set_index("maç")[[metric]].iloc[::-1]
            st.bar_chart(chart)
        st.dataframe(ser.dropna(axis=1, how="all"), hide_index=True, width="stretch")

with tabs[len(tables) + 1]:
    tr = store.select("trends", [("league", "eq", lg)])
    if not tr:
        st.caption("Seri tablosu henüz hesaplanmadı (bot çalışınca dolar).")
    else:
        mk = st.selectbox("Pazar", sorted({x["market"] for x in tr}))
        rows = sorted([x for x in tr if x["market"] == mk], key=lambda x: -x["streak"])
        st.dataframe(pd.DataFrame([{
            "Takım": x["team_name"], "Koşul": x["condition"],
            "Seri": (f"{x['streak']} maçtır tutuyor" if x["streak"] > 0 else f"{-x['streak']} maçtır tutmuyor"),
            "Son 10'da": x["hits_last10"],
            "Maç maç değerler (yeniden eskiye)": " · ".join(f"{v['değer']}" if v["değer"] is not None else "—" for v in x["match_values"]),
        } for x in rows]), hide_index=True, width="stretch")
