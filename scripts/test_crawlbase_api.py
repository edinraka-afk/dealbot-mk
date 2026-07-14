#!/usr/bin/env python3
"""
Single-request smoke test for Crawlbase Crawling API against reklama5.mk.
Prints the page status, credits consumed, and an HTML snippet so we can
verify real listing content reaches us before committing to full scraper changes.

Requires env var: CRAWLBASE_JS_TOKEN (the JavaScript token from your Crawlbase dashboard).
"""
import os
import sys
import requests

TOKEN = os.environ.get("CRAWLBASE_JS_TOKEN", "").strip()
if not TOKEN:
    sys.exit("ERROR: CRAWLBASE_JS_TOKEN is not set")

URL = "https://www.reklama5.mk/Search?cat=24&page=1"

LISTING_MARKERS = ["oglasresults", "oglascell", "oglas", "cena"]
BLOCK_MARKERS   = ["just a moment", "captcha", "access denied", "cloudflare"]

print(f"Token suffix : ...{TOKEN[-6:]}")
print(f"Target URL   : {URL}")
print()

resp = requests.get(
    "https://api.crawlbase.com",
    params={"token": TOKEN, "url": URL},
    timeout=120,
)

pc_status = resp.headers.get("pc-status", "N/A")
credits    = resp.headers.get("pc-credits-used", "N/A")
html       = resp.text
html_lower = html.lower()

print(f"Crawlbase HTTP status : {resp.status_code}")
print(f"Original page status  : {pc_status}")
print(f"Credits used          : {credits}")
print(f"HTML length           : {len(html):,} chars")
print()

found_listing = [m for m in LISTING_MARKERS if m in html_lower]
found_block   = [m for m in BLOCK_MARKERS   if m in html_lower]

if found_listing and not found_block:
    print(f"RESULT: PASS — listing markers found: {found_listing}")
elif found_block:
    print(f"RESULT: BLOCKED — block markers found: {found_block}")
    if found_listing:
        print(f"  (also matched listing markers: {found_listing})")
else:
    print("RESULT: UNKNOWN — neither listing nor block markers found")

print()
print("--- HTML snippet (first 3 000 chars) ---")
print(html[:3000])
