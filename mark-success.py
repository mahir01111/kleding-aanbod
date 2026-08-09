import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
state_path = BASE / "cloud-state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["last_success_at"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
products = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
old_history = json.loads((BASE / "listing-history.json").read_text(encoding="utf-8")) if (BASE / "listing-history.json").exists() else {"products": {}}
merged = old_history.get("products", {})
for row in products:
    merged[row["url"]] = {
        "price": row["price"], "name": row["name"], "evidence_version": row.get("evidence_version", 1),
        "price_observations": row.get("price_observations", []),
        "lowest_observed_price": row.get("lowest_observed_price", row["price"]),
        "sweat_evidence_score": row.get("sweat_evidence_score", 0)
    }
history = {"updated_at": datetime.now(timezone.utc).isoformat(), "products": merged}
(BASE / "listing-history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
