export type Json = Record<string, unknown>;

export interface Match {
  id: string;
  league: string;
  season: string | null;
  kickoff_at: string;
  home_team_id: string;
  away_team_id: string;
  home_name: string;
  away_name: string;
  home_goals: number | null;
  away_goals: number | null;
  score: string | null;
  ht_home_goals: number | null;
  ht_away_goals: number | null;
  status: string;
  durum: string;
  venue: string | null;
  referee: string | null;
  city: string | null;
  odds: Record<string, Record<string, number | string>>;
  sources: Json;
  missing_fields: string[];
  completeness: number | null;
  updated_at: string;
}

export type PredStatus = "bekliyor" | "basladi" | "kazandi" | "kaybetti" | "iade";
export type Tag = "meclis_gorusu" | "gunun_karari" | "karar_birligi";

export interface Prediction {
  id: string;
  recorded_at: string;
  match_id: string;
  kickoff_at: string;
  league: string | null;
  home_name: string | null;
  away_name: string | null;
  tag: Tag;
  coupon_id: string | null;
  market: string;
  selection: string;
  line: number | null;
  probability: number;
  odds: number | null;
  odds_source: string | null;
  fair_odds: number | null;
  edge: number | null;
  confidence: number | null;
  stake: number;
  rationale: string | null;
  scenario_note: string | null;
  completeness: number | null;
  model_version: string | null;
  status: PredStatus;
  result_value: string | null;
  profit: number | null;
  closing_odds: number | null;
  clv: number | null;
  settled_at: string | null;
}

export interface Coupon {
  id: string;
  created_at: string;
  coupon_date: string;
  tag: "gunun_karari" | "karar_birligi";
  total_odds: number;
  joint_probability: number | null;
  legs_count: number;
  stake: number;
  first_kickoff_at: string;
  odds_source: string | null;
  model_version: string | null;
  note: string | null;
  status: PredStatus;
  profit: number | null;
  settled_at: string | null;
}

export interface QueueItem {
  match_id: string;
  status: "bekliyor" | "ertelendi" | "tamamlandi" | "yetismedi";
  missing: string[];
  attempts: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  note: string | null;
}

export interface MatchStat {
  match_id: string;
  side: "home" | "away";
  team_id: string;
  shots: number | null;
  shots_on_target: number | null;
  corners: number | null;
  fouls: number | null;
  yellow: number | null;
  red: number | null;
  goal_kicks: number | null;
  xg: number | null;
  possession: number | null;
}

export interface Injury {
  id: string;
  match_id: string | null;
  team_id: string;
  team_name: string | null;
  player_name: string;
  injury_status: string | null;
  reason: string | null;
  matches_played: number | null;
  key_matches: number | null;
  goal_contribution: number | null;
  defensive_contribution: number | null;
  minutes_share: number | null;
  weight_score: number | null;
  is_key: boolean | null;
  source: string | null;
  fetched_at: string;
}

export interface LineupPlayer { name: string; pos?: string; number?: number; ai_score?: number }
export interface Lineup {
  match_id: string;
  side: "home" | "away";
  formation: string | null;
  start_xi: LineupPlayer[];
  subs: LineupPlayer[];
  coach: string | null;
  source: string | null;
  lineup_status?: string | null;
}

export interface Weather {
  match_id: string;
  data: {
    summary?: string; temperature_c?: number; precip_prob?: number; precip_mm?: number;
    wind_kmh?: number; humidity?: number; location?: string; time_utc?: string; approx?: string;
  };
  source: string | null;
}

export interface Trend {
  id: string;
  team_id: string;
  team_name: string;
  league: string;
  market: string;
  condition: string | null;
  streak: number;
  hits_last10: number | null;
  match_values: { tarih: string; rakip: string; yer: string; değer: number | null }[];
  updated_at: string;
}

export interface Agenda {
  id: string;
  title: string;
  link: string;
  source: string | null;
  published_at: string | null;
  summary: string | null;
  category: string | null;
  match_id: string | null;
  match_ids: string[];
  team_ids: string[];
  impact_note: string | null;
}

export interface Team {
  id: string; league: string; name: string; stadium: string | null; city: string | null;
  coach?: string | null; capacity?: number | null;
}

export interface MarketRow {
  market: string; selection: string; line: number | null; probability: number;
  fair_odds?: number | null; odds?: number | null; edge?: number | null; odds_source?: string | null;
}

export interface AnalysisPayload {
  ready?: boolean;
  lambdas?: { home: number; away: number };
  markets?: MarketRow[];
  missing?: string[];
  quality?: { score?: number; fields?: Record<string, number>; weights?: Record<string, number> };
  weather?: Weather["data"];
  best_pick?: MarketRow & { kind?: string; confidence?: number };
  narrative?: string;
  scenarios?: { ad: string; anlatım: string; olasılık: number | null }[];
  top_scores?: [string, number][];
  count_info?: Record<string, { home: number; away: number; total: number; dist?: string }>;
  injury_effect?: Record<string, unknown>;
  injuries_known?: boolean;
  postponed_markets?: Record<string, string>;
  h2h?: { tarih: string; maç: string; skor: string; İY?: string }[];
  form?: { home?: FormRow[]; away?: FormRow[] };
}
export interface FormRow { tarih: string; rakip: string; yer: string; skor: string; sonuç: string }
export interface Analysis { match_id: string; created_at: string; model_version: string | null; payload: AnalysisPayload }
