import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for k in ("SUPABASE_URL", "SUPABASE_KEY", "FOOTBALL_DATA_TOKEN", "API_FOOTBALL_KEY", "ODDS_API_KEY", "DEMO_MODE"):
    os.environ.pop(k, None)
