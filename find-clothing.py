import hashlib
import atexit
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "search-profiles.json").read_text(encoding="utf-8"))
PROFILES = CONFIG["profiles"]
UA = "Mozilla/5.0 (compatible; KledingAanbod/1.0)"
_playwright = None
_browser = None


def browser_get(url):
    global _playwright, _browser
    from playwright.sync_api import sync_playwright
    if _browser is None:
        _playwright = sync_playwright().start()
        launch = {"headless": True}
        local_chromes = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        local_chrome = next((path for path in local_chromes if os.path.exists(path)), None)
        if local_chrome:
            launch["executable_path"] = local_chrome
        _browser = _playwright.chromium.launch(**launch)
    page = _browser.new_page(user_agent=UA, locale="nl-NL")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)
        return page.content()
    finally:
        page.close()


def close_browser():
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()


atexit.register(close_browser)


def get(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.7"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except Exception as error:
        print(f"Direct ophalen geblokkeerd; browserfallback voor {url}: {error}")
        return browser_get(url)


def search(query, domain):
    links = []
    search_term = f"site:{domain} {query}"
    # Twee onafhankelijke zoekroutes: blokkade of lege resultaten bij één bron stopt de winkel niet.
    for url in (
        "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote(search_term),
        "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(search_term),
    ):
        try:
            page = get(url)
            if "format=rss" in url:
                root = ET.fromstring(page)
                candidates = [node.text or "" for node in root.findall(".//item/link")]
            else:
                soup = BeautifulSoup(page, "html.parser")
                candidates = [a.get("href", "") for a in soup.select("a[href]")]
            for link in candidates:
                if link.startswith("//"):
                    link = "https:" + link
                parsed = urllib.parse.urlparse(link)
                if parsed.netloc.endswith("duckduckgo.com"):
                    link = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
                host = urllib.parse.urlparse(link).netloc.lower().removeprefix("www.")
                if host.endswith(domain):
                    links.append(link)
        except Exception as error:
            print(f"Zoekroute overgeslagen voor {domain}: {error}")
        if links:
            break
    return list(dict.fromkeys(links))


def selectable_sizes(soup):
    """Alleen zichtbaar selecteerbare maatknoppen tellen; maattabeltekst telt niet."""
    sizes = []
    for node in soup.select("button, option, input, label, [role='radio'], [role='option']"):
        label = " ".join(filter(None, (node.get("aria-label"), node.get("value"), node.get_text(" ", strip=True))))
        linked_input = node.find("input") if node.name == "label" else None
        disabled = node.has_attr("disabled") or node.get("aria-disabled", "").lower() == "true" or "disabled" in node.get("class", []) or bool(linked_input and (linked_input.has_attr("disabled") or linked_input.get("aria-disabled", "").lower() == "true"))
        match = re.search(r"(?<![A-Z0-9])(XXL|2XL|XL)(?:\s+(?:Short|Tall|\d+\s*CM))?(?![A-Z0-9])", label, re.I)
        if match and not disabled:
            sizes.append(match.group(0).strip())
    return sorted(set(sizes))


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def product_from_page(url, force_browser=False):
    soup = BeautifulSoup(browser_get(url) if force_browser else get(url), "html.parser")
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    lower_url = url.lower()
    visible = soup.get_text(" ", strip=True)
    ships_to_nl = bool(host.endswith(".nl") or host.startswith("nl.") or any(marker in lower_url for marker in ("/nl/", "/nl-nl/", "/nl_nl/")) or any(term in visible.lower() for term in ("levering in nederland", "bezorging in nederland", "netherlands", "geen douanekosten", "no customs")))
    live_sizes = selectable_sizes(soup)
    nodes = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            nodes.extend(walk_json(json.loads(script.string or script.get_text())))
        except (json.JSONDecodeError, TypeError):
            continue
    product = next((node for node in nodes if any(kind in ([node.get("@type")] if isinstance(node.get("@type"), str) else node.get("@type", [])) for kind in ("Product", "ProductGroup"))), None)
    if not product:
        def meta(*keys):
            for key in keys:
                tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
                if tag and tag.get("content"):
                    return tag["content"].strip()
            return ""
        name = meta("og:title", "twitter:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        description = meta("og:description", "description", "twitter:description")
        raw_price = meta("product:price:amount", "og:price:amount")
        if not raw_price:
            match = re.search(r"(?:€|EUR)\s*([0-9]{1,3}(?:[.,][0-9]{2})?)|([0-9]{1,3}(?:[.,][0-9]{2})?)\s*(?:€|EUR)", visible)
            raw_price = next((group for group in match.groups() if group), "") if match else ""
        try:
            price = float(raw_price.replace(",", "."))
        except (TypeError, ValueError):
            return None
        brand = next((brand for brand in ("Adidas", "Nike", "Under Armour", "Puma", "Reebok", "ASICS") if brand.lower() in f"{name} {description}".lower()), host.split(".")[0].title())
        return {
            "url": url, "name": name[:240], "brand": brand,
            "description": f"{description} {visible}"[:7000], "color": meta("product:color", "color"),
            "material": "", "review_text": "", "rating_value": None, "review_count": None,
            "available_sizes": live_sizes, "image": meta("og:image", "twitter:image"), "price": price,
            "currency": meta("product:price:currency") or "EUR", "availability": meta("product:availability"), "seller": host, "ships_to_nl": ships_to_nl,
        }
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
    if not image:
        image_meta = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
        image = image_meta.get("content", "") if image_meta else ""
    price = offer.get("price") or offer.get("lowPrice")
    try:
        price = float(str(price).replace(",", "."))
    except (TypeError, ValueError):
        price = None
    if price is None:
        price_match = re.search(r"(?:€|EUR)\s*([0-9]{1,3}(?:[.,][0-9]{2})?)|([0-9]{1,3}(?:[.,][0-9]{2})?)\s*(?:€|EUR)", visible)
        price = float(next(group for group in price_match.groups() if group).replace(",", ".")) if price_match else None
    reviews = product.get("review") or []
    if isinstance(reviews, dict):
        reviews = [reviews]
    review_text = " ".join(str(r.get("reviewBody") or "") for r in reviews[:12] if isinstance(r, dict))
    aggregate = product.get("aggregateRating") or {}
    variants = product.get("hasVariant") or []
    if isinstance(variants, dict):
        variants = [variants]
    variant_color = next((str(v.get("color")) for v in variants if isinstance(v, dict) and v.get("color")), "")
    positive_notes = product.get("positiveNotes") or []
    if isinstance(positive_notes, str):
        positive_notes = [positive_notes]
    return_policy = product.get("hasMerchantReturnPolicy") or {}
    return_days = return_policy.get("merchantReturnDays") if isinstance(return_policy, dict) else None
    material = str(product.get("material") or "")
    if not material:
        material_match = re.search(r"(?:materiaal[^.%]{0,100})?\b(\d{2,3}%\s*(?:gerecycled\s+)?(?:polyester|polyamide|nylon))", visible, re.I)
        material = material_match.group(1) if material_match else ""
    available_sizes = []
    for node in nodes:
        node_type = node.get("@type") if isinstance(node, dict) else None
        if node_type != "Product" or not node.get("size"):
            continue
        node_offer = node.get("offers") or {}
        if isinstance(node_offer, list):
            node_offer = node_offer[0] if node_offer else {}
        if "instock" in str(node_offer.get("availability", "")).lower():
            available_sizes.append(str(node["size"]))
    return {
        "url": url, "name": str(product.get("name") or "").strip(), "brand": str(brand).strip(),
        "description": (BeautifulSoup(str(product.get("description") or ""), "html.parser").get_text(" ", strip=True) + " " + " ".join(map(str, positive_notes)) + (f" {return_days} dagen retour" if return_days else "")).strip(),
        "color": str(product.get("color") or variant_color), "material": material,
        "review_text": review_text[:2500], "rating_value": aggregate.get("ratingValue"),
        "review_count": aggregate.get("reviewCount") or aggregate.get("ratingCount"),
        "available_sizes": sorted(set(available_sizes + live_sizes)),
        "image": str(image), "price": price, "currency": offer.get("priceCurrency", "EUR"),
        "availability": str(offer.get("availability") or ""), "seller": host, "ships_to_nl": ships_to_nl,
    }


def discover_page(url, allowed_domains):
    soup = BeautifulSoup(get(url), "html.parser")
    links = []
    for anchor in soup.select("a[href]"):
        link = urllib.parse.urljoin(url, anchor.get("href"))
        host = urllib.parse.urlparse(link).netloc.lower().removeprefix("www.")
        product_shape = "/p/" in link or "/product/" in link or "/products/" in link or link.split("?", 1)[0].endswith(".html")
        if any(host.endswith(domain) for domain in allowed_domains) and product_shape:
            clean = link.split("#", 1)[0]
            if "dwvar_" not in clean:
                clean = clean.split("?", 1)[0]
            links.append(clean)
    return list(dict.fromkeys(links))


def score(item, profile):
    text = f"{item['name']} {item['brand']} {item['description']} {item['color']} {item['material']} {item['review_text']}".lower()
    product_text = f"{item['name']} {item['brand']} {item['description']} {item['color']} {item['material']}".lower()
    if item["price"] is None or item["price"] > profile["max_price_eur"]:
        return None
    if profile["required_any"] and not any(term.lower() in text for term in profile["required_any"]):
        return None
    if any(term.lower() in product_text for term in profile["blocked"]):
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
    safe_color = any(x.lower() in product_text for x in profile.get("safe_colors", []))
    technical = any(x in product_text for x in ("vochtafvoerend", "moisture wicking", "dri-fit", "dry fit", "sneldrogend", "quick dry", "actibreeze"))
    synthetic = any(x in product_text for x in ("polyester", "polyamide", "nylon", "elastane", "elastaan"))
    if not safe_color or not technical or not synthetic:
        return None
    review_sweat = any(x in item.get("review_text", "").lower() for x in ("sweat", "zweet", "wet mark", "vochtplek", "sweat mark"))
    if not any(x in text for x in ("vochtafvoerend", "moisture wicking", "dri-fit", "dry fit", "sneldrogend", "quick dry")):
        concerns.append("Geen expliciet bewijs voor vochtafvoer of sneldrogen")
    if not any(x in text for x in ("zwart", "black", "gemêleerd", "print", "pattern")):
        concerns.append("Kleur/patroon biedt geen duidelijk bewijs tegen zichtbare zweetvlekken")
    item.update({"local_score": min(points, 100), "evidence": sorted(set(evidence)), "concerns": concerns})
    item["category"] = "korte sportbroek" if any(x in product_text for x in ("shorts", "korte broek")) else "sportshirt"
    item["size_advice"] = "Waarschijnlijk XL of 2XL; alleen kopen na controle van borst/taille/heup in de merkmaattabel"
    item["sale"] = any(x in text for x in ("sale", "aanbieding", "korting", "van €", "original price"))
    item["purchase_ready"] = True
    item["sweat_mark_confidence"] = "sterk" if review_sweat else "redelijk"
    item["research_basis"] = ["donkere of patroonrijke kleur", "expliciet vochtafvoerend/sneldrogend", "synthetisch technisch materiaal"] + (["relevante gebruikersreview"] if review_sweat else [])
    item["purchase_ready"] = bool(item.get("image") and any(re.match(r"^(?:xl|xxl|2xl)(?:\s|$)", size.lower()) for size in item.get("available_sizes", [])))
    return item


verified_path = BASE / "verified-products.json"
results = json.loads(verified_path.read_text(encoding="utf-8")) if verified_path.exists() else []
seen = {row["url"] for row in results}
if os.environ.get("VERIFIED_ONLY", "").lower() == "true":
    (BASE / "products.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} gecontroleerde kledingproducten opgeslagen.")
    raise SystemExit(0)
for profile in (p for p in PROFILES if p.get("enabled")):
    for clean in profile.get("seed_products", []):
        if clean in seen:
            continue
        seen.add(clean)
        try:
            item = product_from_page(clean, force_browser=True)
            if item and (item := score(item, profile)):
                item["profile_id"] = profile["id"]
                item["candidate_id"] = "K" + hashlib.sha256(clean.encode()).hexdigest()[:8].upper()
                results.append(item)
        except Exception as error:
            print(f"Vast winkelproduct overgeslagen ({clean}): {error}")
    discovered = []
    for page in profile.get("discovery_pages", []):
        try:
            page_links = discover_page(page, profile["retailer_domains"])
            print(f"{len(page_links)} productlinks op collectiepagina {page}", flush=True)
            discovered.extend(page_links[:12])
        except Exception as error:
            print(f"Collectiepagina overgeslagen ({page}): {str(error)[:300]}")
    for clean in list(dict.fromkeys(discovered))[:30]:
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
    focused_queries = profile["queries"][:2] + [q for q in profile["queries"] if "short" in q.lower()][:1]
    # Doorzoek dagelijks een andere brede winkelbatch. Zo blijft de run snel, terwijl alle winkels
    # cyclisch aan bod komen en de vaste officiële product- en collectiebronnen elke dag draaien.
    domains = profile["retailer_domains"]
    batch_size = min(12, len(domains))
    start = (date.today().toordinal() * batch_size) % len(domains)
    search_domains = [domains[(start + offset) % len(domains)] for offset in range(batch_size)]
    for query in focused_queries:
        for domain in search_domains:
            try:
                urls = search(query, domain)
            except Exception as error:
                print(f"Zoeken mislukt voor {query!r} op {domain}: {error}")
                continue
            for url in urls[:3]:
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
# Eén merk mag de kandidaatpool niet vullen; maximaal zes varianten per merk vóór DeepSeek.
diverse, brand_counts = [], {}
for row in results:
    brand = (row.get("brand") or row.get("seller") or "onbekend").lower()
    if brand_counts.get(brand, 0) >= 6:
        continue
    brand_counts[brand] = brand_counts.get(brand, 0) + 1
    diverse.append(row)
(BASE / "products.json").write_text(json.dumps(diverse[:40], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(diverse[:40])} passende kledingproducten van {len(brand_counts)} merken opgeslagen.")
