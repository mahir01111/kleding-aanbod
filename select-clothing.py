import json
import os
import re
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
config = json.loads((BASE / "search-profiles.json").read_text(encoding="utf-8"))
source = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
if not source:
    (BASE / "selection.json").write_text('{"winner_id": null, "source": "geen kandidaten", "ratings": []}\n', encoding="utf-8")
    print("Geen producten voor beoordeling; AI niet aangeroepen.")
    raise SystemExit(0)

fields = ("candidate_id", "category", "name", "brand", "price", "sale", "seller", "description", "color", "material", "rating_value", "review_count", "review_text", "local_score", "evidence", "concerns", "size_advice", "available_sizes", "image")
candidates = [{key: row.get(key) for key in fields} for row in source[:20]]
ids = [row["candidate_id"] for row in candidates]
fallback = {
    "winner_id": source[0]["candidate_id"], "source": "lokale score",
    "ratings": [{"candidate_id": row["candidate_id"], "stars": 4 if row["local_score"] >= 75 else 3 if row["local_score"] >= 55 else 2, "reason": "; ".join(row["evidence"][:4]) or "Beperkte productinformatie"} for row in source[:20]],
}
output = BASE / "selection.json"
output.write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
token = os.environ.get("OPENROUTER_API_KEY")
if not token:
    print("Geen OpenRouter-sleutel: lokale selectie gebruikt.")
    raise SystemExit(0)

prompt = """Je bent een uiterst kritische Nederlandse aankoopagent voor sportkleding. De koper is een gespierde man van 38 jaar, 183 cm en 100 kg. Zoek T-shirts en korte broeken voor intensieve training waarbij vochtplekken zo min mogelijk zichtbaar worden. Doe geen marketingaannames. Betrouwbaar advies vereist zowel een donkere, gemêleerde of druk bedrukte kleur die nat-droogcontrast beperkt als expliciet sneldrogend of vochtafvoerend technisch materiaal. Reviews over zweet, natte plekken, ademend vermogen en pasvorm wegen zwaar. Katoenrijke of lichte effen kleding is ongeschikt. XL-2XL is slechts een zoekvenster; zonder borst-, taille- en heupmaat mag je geen maat garanderen. Een aanbieding komt hoger bij gelijke geschiktheid, maar korting mag nooit een zwakker product winnen. Geef 4 sterren alleen bij sterk concreet bewijs, 3 bij behoorlijk bewijs met kleine onzekerheid, 2 bij wezenlijke onzekerheid en 1 bij afwijzen. Verzin geen review, korting, maat of eigenschap. Gebruik alleen candidate_id, nooit URL's. Antwoord uitsluitend als JSON met winner_id en ratings (candidate_id, stars, reason)."""
user_data = {"shopper": config["shopper"], "candidates": candidates}
payload = {"model": "openrouter/free", "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(user_data, ensure_ascii=False)}], "temperature": 0.1, "max_tokens": 4000}
request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(payload).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Title": "Kleding Aanbod"})
try:
    with urllib.request.urlopen(request, timeout=90) as response:
        content = json.loads(response.read())["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    result = json.loads(content)
    ratings = result.get("ratings", [])
    rated = [row.get("candidate_id") for row in ratings]
    if result.get("winner_id") not in ids or set(rated) != set(ids) or len(rated) != len(ids):
        raise ValueError("AI gebruikte niet exact alle kandidaatcodes")
    if not all(isinstance(row.get("stars"), int) and 1 <= row["stars"] <= 4 for row in ratings):
        raise ValueError("AI gaf ongeldige sterren")
    result["source"] = "OpenRouter gratis AI"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
except Exception as error:
    print(f"AI niet bruikbaar; lokale selectie blijft actief: {error}")
