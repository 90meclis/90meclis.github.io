import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Proje adresi gizli değildir. Anahtar derleme anında GitHub Actions secret'ından gelir
// (SUPABASE_PUBLISHABLE_KEY → VITE_SUPABASE_PUBLISHABLE_KEY). Yalnızca publishable/anon anahtar: RLS ile salt okunur.
const URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined) || "https://fwispwtdqapmnkcjisek.supabase.co";
const KEY = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined) || "";

export const supabase: SupabaseClient | null = KEY
  ? createClient(URL, KEY, {
      auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

export const hasData = supabase !== null;
