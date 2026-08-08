import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
report = (BASE / "kleding-aanbod.html").read_text(encoding="utf-8")
products = json.loads((BASE / "products.json").read_text(encoding="utf-8"))
now = datetime.now().astimezone()
payload = {
    "from": "Kleding aanbod <onboarding@resend.dev>",
    "to": [os.environ["CLOTHING_MAIL_TO"]],
    "subject": f"Kleding-aanbod – {len(products)} passende sportshirts – {now:%d-%m-%Y}",
    "html": report,
    "text": f"Er zijn {len(products)} passende sportshirts gevonden. Open deze mail in HTML-weergave voor foto's en links."
}
request = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(), method="POST", headers={
    "Authorization": f"Bearer {os.environ['CLOTHING_RESEND_API_KEY']}",
    "Content-Type": "application/json", "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; KledingAanbod/1.0; +https://github.com/mahir01111/kleding-aanbod)",
    "Idempotency-Key": f"kleding-{os.environ.get('GITHUB_RUN_ID', now.strftime('%Y%m%d%H%M%S'))}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}",
})
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        print(response.read().decode())
except urllib.error.HTTPError as error:
    detail = error.read().decode("utf-8", errors="replace")
    raise SystemExit(f"Resend gaf HTTP {error.code}: {detail}") from error
