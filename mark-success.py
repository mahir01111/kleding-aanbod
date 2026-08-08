import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
state_path = BASE / "cloud-state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["last_success_at"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
products = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
history = {"updated_at": datetime.now(timezone.utc).isoformat(), "products": {row["url"]: {"price": row["price"], "name": row["name"]} for row in products}}
(BASE / "listing-history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
