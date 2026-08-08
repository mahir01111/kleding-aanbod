import json
import os
from datetime import datetime, timezone
from pathlib import Path

PATH = Path(__file__).with_name("cloud-state.json")
MAX_RUNS = 10
MINIMUM_HOURS = 72
force = os.environ.get("FORCE_RUN", "").lower() == "true"
now = datetime.now(timezone.utc)
month = now.strftime("%Y-%m")
state = json.loads(PATH.read_text(encoding="utf-8"))
if state.get("month") != month:
    state = {"month": month, "reserved_runs": 0, "last_reserved_at": None, "last_success_at": None}

allowed = state["reserved_runs"] < MAX_RUNS
reason = "maandlimiet bereikt"
if allowed and state.get("last_reserved_at") and not force:
    elapsed = (now - datetime.fromisoformat(state["last_reserved_at"])).total_seconds()
    allowed = elapsed >= MINIMUM_HOURS * 3600
    reason = f"minder dan {MINIMUM_HOURS} uur sinds de vorige kledingrun"
if allowed:
    state["reserved_runs"] += 1
    state["last_reserved_at"] = now.isoformat()
    PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Kledingrun {state['reserved_runs']}/{MAX_RUNS} gereserveerd.")
else:
    print(f"Geen kledingrun: {reason}.")

if output := os.environ.get("GITHUB_OUTPUT"):
    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"allowed={'true' if allowed else 'false'}\n")
        handle.write(f"run_number={state['reserved_runs']}\n")
