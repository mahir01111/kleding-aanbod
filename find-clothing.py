import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "search-profiles.json").read_text(encoding="utf-8"))
PROFILES = CONFIG["profiles"]
UA = "Mozilla/5.0 (compatible; KledingAanbod/1.0)"


def get(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.7"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def search(query, domain):
    url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote(f"site:{domain} {query}")
    root = ET.fromstring(get(url))
    links = [item.findtext("link") for item in root.findall(".//item") if item.findtext("link")]
    return [link for link in links if urllib.parse.urlparse(link).netloc.lower().removeprefix("www.").endswith(domain)]


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def product_from_page(url):
    soup = BeautifulSoup(get(url), "html.parser")
    nodes = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            nodes.extend(walk_json(json.loads(script.string or script.get_text())))
        except (json.JSONDecodeError, TypeError):
            continue
    product = next((node for node in nodes if "Product" in ([node.get("@type")] if isinstance(node.get("@type"), str) else node.get("@type", []))), None)
    if not product:
        return None
    offer = product.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    brand = product.get("brand") or ""
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    image = product.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url", "")
    price = offer.get("price") or offer.get("lowPrice")
    try:
        price = float(str(price).replace(",", "."))
    except (TypeError, ValueError):
        price = None
    reviews = product.get("review") or []
    if isinstance(reviews, dict):
        reviews = [reviews]
    review_text = " ".join(str(r.get("reviewBody") or "") for r in reviews[:12] if isinstance(r, dict))
    aggregate = product.get("aggregateRating") or {}
    return {
        "url": url, "name": str(product.get("name") or "").strip(), "brand": str(brand).strip(),
        "description": BeautifulSoup(str(product.get("description") or ""), "html.parser").get_text(" ", strip=True),
        "color": str(product.get("color") or ""), "material": str(product.get("material") or ""),
        "review_text": review_text[:2500], "rating_value": aggregate.get("ratingValue"),
        "review_count": aggregate.get("reviewCount") or aggregate.get("ratingCount"),
        "image": str(image), "price": price, "currency": offer.get("priceCurrency", "EUR"),
        "availability": str(offer.get("availability") or ""), "seller": urllib.parse.urlparse(url).netloc.removeprefix("www."),
    }


def discover_page(url, allowed_domains):
    soup = BeautifulSoup(get(url), "html.parser")
    links = []
    for anchor in soup.select("a[href]"):
        link = urllib.parse.urljoin(url, anchor.get("href"))
        host = urllib.parse.urlparse(link).netloc.lower().removeprefix("www.")
        if any(host.endswith(domain) for domain in allowed_domains) and ("/p/" in link or "/product/" in link or "/products/" in link):
            links.append(link.split("?", 1)[0].split("#", 1)[0])
    return list(dict.fromkeys(links))


def score(item, profile):
    text = f"{item['name']} {item['brand']} {item['description']} {item['color']} {item['material']} {item['review_text']}".lower()
    if item["price"] is None or item["price"] > profile["max_price_eur"]:
        return None
    if profile["required_any"] and not any(term.lower() in text for term in profile["required_any"]):
        return None
    if any(term.lower() in text for term in profile["blocked"]):
        return None
    points, evidence, concerns = 10, [], []
    signals = {
        "vochtafvoerend": 18, "moisture wicking": 18, "dri-fit": 18, "dry fit": 16,
        "sneldrogend": 14, "quick dry": 14, "ademend": 10, "breathable": 10,
        "polyester": 8, "polyamide": 8, "mesh": 7, "zwart": 15, "black": 15,
        "donkerblauw": 12, "navy": 12, "midnight": 12, "gemêleerd": 10, "print": 8, "pattern": 8,
    }
    for term, value in signals.items():
        if term in text:
            points += value
            evidence.append(term)
    if item["brand"].lower() in {x.lower() for x in profile["preferred_brands"]}:
        points += 5
    safe_color = any(x.lower() in text for x in profile.get("safe_colors", []))
    technical = any(x in text for x in ("vochtafvoerend", "moisture wicking", "dri-fit", "dry fit", "sneldrogend", "quick dry", "actibreeze"))
    synthetic = any(x in text for x in ("polyester", "polyamide", "nylon", "elastane", "elastaan"))
    if not safe_color or not technical or not synthetic:
        return None
    review_sweat = any(x in item.get("review_text", "").lower() for x in ("sweat", "zweet", "wet mark", "vochtplek", "sweat mark"))
    if not any(x in text for x in ("vochtafvoerend", "moisture wicking", "dri-fit", "dry fit", "sneldrogend", "quick dry")):
        concerns.append("Geen expliciet bewijs voor vochtafvoer of sneldrogen")
    if not any(x in text for x in ("zwart", "black", "gemêleerd", "print", "pattern")):
        concerns.append("Kleur/patroon biedt geen duidelijk bewijs tegen zichtbare zweetvlekken")
    item.update({"local_score": min(points, 100), "evidence": sorted(set(evidence)), "concerns": concerns})
    item["category"] = "korte sportbroek" if any(x in text for x in ("short", "korte broek")) else "sportshirt"
    item["size_advice"] = "Waarschijnlijk XL of 2XL; alleen kopen na controle van borst/taille/heup in de merkmaattabel"
    item["sale"] = any(x in text for x in ("sale", "aanbieding", "korting", "van €", "original price"))
    item["purchase_ready"] = True
    item["sweat_mark_confidence"] = "sterk" if review_sweat else "redelijk"
    item["research_basis"] = ["donkere of patroonrijke kleur", "expliciet vochtafvoerend/sneldrogend", "synthetisch technisch materiaal"] + (["relevante gebruikersreview"] if review_sweat else [])
    return item


results = []
seen = set()
for profile in (p for p in PROFILES if p.get("enabled")):
    discovered = []
    for page in profile.get("discovery_pages", []):
        try:
            discovered.extend(discover_page(page, profile["retailer_domains"]))
        except Exception as error:
            print(f"Collectiepagina overgeslagen ({page}): {error}")
    for clean in list(dict.fromkeys(discovered))[:60]:
        if clean in seen:
            continue
        seen.add(clean)
        try:
            item = product_from_page(clean)
            if item and (item := score(item, profile)):
                item["profile_id"] = profile["id"]
                item["candidate_id"] = "K" + hashlib.sha256(clean.encode()).hexdigest()[:8].upper()
                results.append(item)
        except Exception as error:
            print(f"Product overgeslagen ({clean}): {error}")
        time.sleep(0.08)
    for query in profile["queries"]:
        for domain in profile["retailer_domains"]:
            try:
                urls = search(query, domain)
            except Exception as error:
                print(f"Zoeken mislukt voor {query!r} op {domain}: {error}")
                continue
            for url in urls[:4]:
                clean = url.split("#", 1)[0]
                if clean in seen:
                    continue
                seen.add(clean)
                try:
                    item = product_from_page(clean)
                    if item and (item := score(item, profile)):
                        item["profile_id"] = profile["id"]
                        item["candidate_id"] = "K" + hashlib.sha256(clean.encode()).hexdigest()[:8].upper()
                        results.append(item)
                except Exception as error:
                    print(f"Product overgeslagen ({clean}): {error}")
                time.sleep(0.1)

results.sort(key=lambda row: (not row.get("sale", False), -row["local_score"], row["price"]))
(BASE / "products.json").write_text(json.dumps(results[:30], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(results[:30])} passende kledingproducten opgeslagen.")
