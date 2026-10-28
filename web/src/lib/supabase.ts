import { statikdb, type StatikDb } from "./statikdb";

// Site artık hiçbir veritabanına bağlanmaz: bütün okumalar `veri` dalındaki statik JSON dosyalarından yapılır
// (bkz. lib/statikdb.ts, meclis/statik_q.py). Ad, mevcut çağrıları değiştirmemek için korunur.
export const supabase: StatikDb | null = statikdb;
export const hasData = true;
