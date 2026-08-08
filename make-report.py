import html
import json
import os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
all_products = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
selection = json.loads((BASE / "selection.json").read_text(encoding="utf-8")) if (BASE / "selection.json").exists() else {}
history = json.loads((BASE / "listing-history.json").read_text(encoding="utf-8"))
old = history.get("products", {})
ratings = {row["candidate_id"]: row for row in selection.get("ratings", [])}
winner_id = selection.get("winner_id")
def likely_size(size):
    return bool(__import__("re").match(r"^(?:xl|xxl|2xl)(?:\s|$)", str(size).lower()))


products = [row for row in all_products if row.get("purchase_ready") and row.get("image") and any(likely_size(size) for size in row.get("available_sizes", [])) and int(ratings.get(row["candidate_id"], {}).get("stars", 0)) >= 3]
new_or_lower = [row for row in products if row["url"] not in old or row["price"] < old[row["url"]].get("price", float("inf")) or row.get("evidence_version", 1) > old[row["url"]].get("evidence_version", 0)]


def card(row):
    rating = ratings.get(row["candidate_id"], {})
    stars_count = int(rating.get("stars", 1))
    stars = "★" * stars_count + "☆" * (4 - stars_count)
    winner = '<div class="winner">UITBLINKER</div>' if row["candidate_id"] == winner_id else ""
    image = f'<img src="{html.escape(row["image"], quote=True)}" alt="Productfoto">' if row.get("image") else ""
    proof = ", ".join(row.get("evidence", [])) or "weinig concreet bewijs"
    concern = " · ".join(row.get("concerns", []))
    sale = '<span class="sale">AANBIEDING</span>' if row.get("sale") else ""
    return f'''<article>{winner}{image}<div class="body"><h2>{html.escape(row['name'])}</h2>
    <div class="stars">{stars}</div><p class="price">€ {row['price']:.2f} {sale}</p>
    <p><b>Type:</b> {html.escape(row.get('category', 'sportkleding'))}</p>
    <p><b>Merk/winkel:</b> {html.escape(row.get('brand') or 'Onbekend')} · {html.escape(row['seller'])}</p>
    <p><b>Bewijs tegen zichtbare zweetplekken:</b> {html.escape(proof)}</p>
    <p><b>Zekerheidsniveau:</b> {html.escape(row.get('sweat_mark_confidence', 'onbekend'))} — geen absolute garantie</p>
    <p><b>Maatadvies:</b> {html.escape(row.get('size_advice', 'Controleer de merkmaattabel'))}</p>
    <p><b>Nu aangetroffen maten:</b> {html.escape(', '.join(row.get('available_sizes', [])))}</p>
    <p><b>Beoordeling:</b> {html.escape(rating.get('reason', 'Lokale productscore'))}</p>
    {f'<p class="warn"><b>Aandachtspunt:</b> {html.escape(concern)}</p>' if concern else ''}
    <a href="{html.escape(row['url'], quote=True)}">Bekijk bij de winkel</a></div></article>'''


ordered = sorted(products, key=lambda row: (row["candidate_id"] != winner_id, not row.get("sale", False), -row["local_score"], row["price"]))
content = "".join(card(row) for row in ordered[:12]) or "<p>Er zijn deze keer geen voldoende onderbouwde producten gevonden.</p>"
report = f'''<!doctype html><html lang="nl"><head><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;background:#f4f5f7;color:#17202a;margin:0;padding:20px}}main{{max-width:760px;margin:auto}}article{{background:white;border-radius:14px;overflow:hidden;margin:18px 0;box-shadow:0 2px 9px #0002}}img{{width:100%;max-height:380px;object-fit:contain;background:#fafafa}}.body{{padding:18px}}h1{{font-size:26px}}h2{{font-size:20px;margin:3px 0}}.stars{{color:#e49300;font-size:22px}}.price{{font-size:24px;font-weight:bold}}.sale{{font-size:12px;background:#d9480f;color:white;border-radius:5px;padding:4px 7px}}a{{display:inline-block;background:#17202a;color:white;padding:11px 16px;border-radius:8px;text-decoration:none}}.winner{{background:#087f5b;color:white;font-weight:bold;padding:9px 18px}}.warn{{color:#8a3b12}}small{{color:#626b73}}
</style></head><body><main><h1>Sportshirts en korte broeken</h1><p>Voor een gespierde man van 183 cm en 100 kg. Alleen donkere/patroonrijke kleding met expliciet technisch materiaal wordt toegelaten. Aanbiedingen staan hoger bij gelijke geschiktheid.</p><p><b>Belangrijk:</b> volledige onzichtbaarheid van zweet kan online niet worden gegarandeerd. De agent selecteert de laagste aantoonbare kans en benoemt onzekerheid.</p>{content}<small>Gemaakt op {datetime.now().astimezone():%d-%m-%Y %H:%M} · selectie: {html.escape(selection.get('source', 'lokale score'))}</small></main></body></html>'''
(BASE / "kleding-aanbod.html").write_text(report, encoding="utf-8")

should_send = bool(products and (new_or_lower or not old))
if output := os.environ.get("GITHUB_OUTPUT"):
    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"should_send={'true' if should_send else 'false'}\n")
        handle.write(f"product_count={len(products)}\n")
print(f"Rapport met {len(products)} producten; mail={'ja' if should_send else 'nee'}.")
