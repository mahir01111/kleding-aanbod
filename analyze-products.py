import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
products_path = BASE / "products.json"
history_path = BASE / "listing-history.json"
products = json.loads(products_path.read_text(encoding="utf-8"))
history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {"products": {}}
old = history.get("products", {})

POSITIVE = ("geen zweet", "not sweat", "no sweat", "sweat doesn't show", "sweat does not show", "niet zweetgevoelig", "blijft droog", "keeps dry")
NEGATIVE = ("zweetvlek", "sweat mark", "shows sweat", "wet patch", "natte plek", "doorschijn", "see-through", "see through")


def combined(row):
    return " ".join(str(row.get(k, "")) for k in ("name", "description", "color", "material", "review_text")).lower()


def size_match(row):
    sizes = [str(x) for x in row.get("available_sizes", [])]
    likely = [x for x in sizes if re.match(r"^(?:xl|xxl|2xl)(?:\s|$)", x.lower())]
    body = combined(row)
    if not likely:
        return 0, [], "Geen aannemelijke maat op voorraad"
    if any(x in body for x in ("valt klein", "runs small", "strak", "slim fit", "compression")) and not any(x.lower().startswith(("2xl", "xxl")) for x in likely):
        return 35, likely, "Strakke/kleine pasvorm zonder 2XL op voorraad"
    confidence = 68 if row.get("brand") else 55
    if any(x in body for x in ("valt groot", "runs large", "ruim", "loose fit", "relaxed fit")):
        confidence += 7
    return min(confidence, 80), likely, "Voorlopige schatting; lichaamsmaten zijn nog niet gemeten"


def sweat_evidence(row):
    body, reviews = combined(row), str(row.get("review_text", "")).lower()
    positives = [x for x in POSITIVE if x in reviews]
    negatives = [x for x in NEGATIVE if x in reviews]
    technical = any(x in body for x in ("aeroready", "dri-fit", "dry fit", "heatgear", "drycell", "actibreeze", "vochtafvoer", "moisture wick", "sneldrog", "quick dry"))
    synthetic = any(x in body for x in ("polyester", "polyamide", "nylon", "elastaan", "elastane"))
    dark = any(x in body for x in ("black", "zwart", "navy", "donkerblauw", "dark green", "donkergroen", "forest green", "burgundy", "donkerpaars", "antraciet", "pattern", "print", "gemêleerd"))
    score = 20 + 20 * technical + 15 * synthetic + 20 * dark + min(20, len(positives) * 12) - min(45, len(negatives) * 20)
    if int(float(row.get("review_count") or 0)) >= 20:
        score += 5
    reasons = (["expliciete vochtafvoer/sneldrogen"] if technical else []) + (["technische synthetische stof"] if synthetic else []) + (["laag nat-droogcontrast"] if dark else []) + (["relevante positieve review"] if positives else [])
    return max(0, min(score, 100)), reasons, negatives


def return_assessment(row):
    body = combined(row)
    match = re.search(r"(\d{2,3})\s*(?:dagen|days).*retour", body)
    if match:
        days = int(match.group(1))
        return ("laag" if days >= 30 else "middel"), f"{days} dagen genoemd; controleer actuele voorwaarden"
    if any(x in body for x in ("gratis retour", "free returns", "kosteloos retourneren")):
        return "laag", "Gratis retour genoemd; controleer actuele voorwaarden"
    return "onbekend", "Retourvoorwaarden niet betrouwbaar vastgesteld; controleer vóór bestellen"


output, fingerprints = [], set()
for row in products:
    url = row.get("url", "").split("?", 1)[0].rstrip("/")
    fingerprint = hashlib.sha256(re.sub(r"[^a-z0-9]", "", f"{row.get('brand','')} {row.get('name','')} {row.get('color','')}".lower()).encode()).hexdigest()[:16]
    if not url or fingerprint in fingerprints:
        continue
    fingerprints.add(fingerprint)
    row["url"] = url
    sweat_score, reasons, negative_reviews = sweat_evidence(row)
    fit_score, matching_sizes, fit_note = size_match(row)
    return_risk, return_note = return_assessment(row)
    previous = old.get(url, {})
    observations = list(previous.get("price_observations", []))
    current_price = float(row.get("price") or 0)
    if current_price and (not observations or observations[-1].get("price") != current_price):
        observations.append({"at": datetime.now(timezone.utc).isoformat(), "price": current_price})
    observed = [float(x["price"]) for x in observations if x.get("price")]
    prior_high = max(observed[:-1], default=current_price)
    verified_discount = bool(current_price and prior_high > current_price)
    row.update({
        "product_fingerprint": fingerprint, "sweat_evidence_score": sweat_score,
        "sweat_evidence_reasons": reasons, "negative_review_signals": negative_reviews,
        "fit_confidence_score": fit_score, "matching_sizes": matching_sizes, "fit_note": fit_note,
        "return_risk": return_risk, "return_note": return_note,
        "price_observations": observations[-24:], "lowest_observed_price": min(observed, default=current_price),
        "verified_discount": verified_discount,
        "discount_percent": round((prior_high - current_price) / prior_high * 100) if verified_discount else 0,
        "advertised_sale_unverified": bool(row.get("sale")) and not verified_discount,
    })
    row["purchase_ready"] = bool(row.get("image") and matching_sizes and sweat_score >= 65 and not negative_reviews)
    row["local_score"] = round(0.70 * sweat_score + 0.20 * fit_score + 0.10 * min(100, int(float(row.get("rating_value") or 0) * 20)))
    output.append(row)

output.sort(key=lambda r: (r.get("category") != "sportshirt", not r["verified_discount"], -r["local_score"], r.get("price", 9999)))
products_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(output)} unieke producten geanalyseerd; {sum(bool(x['purchase_ready']) for x in output)} koopwaardig.")
