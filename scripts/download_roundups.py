#!/usr/bin/env python3
"""Download AllSides story pages given links in data/links.json.

Saves valid HTML pages into data/roundups_raw and writes a JSON mapping
data/valid_links.json where keys are the original links and values are the
filenames (basename) written in `data/roundups_raw`.

Usage examples:
  python3 scripts/download_roundups.py         # downloads all
  python3 scripts/download_roundups.py --limit 50   # only first 50 links (for testing)
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests


def safe_filename_from_url(url):
    # try to use the slug after /story/ if present
    m = re.search(r"/story/([^/?#]+)", url)
    if m:
        slug = m.group(1)
        # sanitize: keep alnum, dash, underscore
        slug = re.sub(r"[^A-Za-z0-9._-]", "-", slug)
        # truncate to reasonable length
        slug = slug[:120]
        return f"{slug}.html"
    # fallback: sha1
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return f"article_{h}.html"


def looks_like_not_found(text_lower):
    # heuristics for AllSides 'not found' landing page
    checks = [
        "page not found",
        "not found",
        "sorry, the page",
        "could not be found",
        "404",
    ]
    for c in checks:
        if c in text_lower:
            return True
    return False


def download_one(url, out_dir, session, timeout=15):
    try:
        r = session.get(url, timeout=timeout)
    except requests.RequestException as e:
        return None, f"REQUEST_ERROR {e}"

    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"

    raw = r.content
    try:
        text = raw.decode("utf-8")
    except Exception:
        text = raw.decode("latin-1", errors="replace")

    tl = text.lower()
    if looks_like_not_found(tl):
        return None, "not found page"

    # save file
    fname = safe_filename_from_url(url)
    out_path = out_dir / fname
    if out_path.exists():
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        fname = out_path.stem + f"-{h}" + out_path.suffix
        out_path = out_dir / fname

    out_path.write_bytes(raw)
    return fname, None


def main():

    repo_root = Path(__file__).resolve().parents[1]
    links_file = repo_root / "data" / "links.json"
    out_dir = repo_root / "data" / "roundups_raw"
    valid_links_file = repo_root / "data" / "valid_links.json"

    DOWNLOAD_LIMIT = int(os.getenv("DOWNLOAD_LIMIT", "0"))
    REQUEST_SLEEP = float(os.getenv("REQUEST_SLEEP", "0.5"))

    if not links_file.exists():
        print(f"links.json not found at {links_file}. Run extract_links first.")
        return

    links = json.loads(links_file.read_text(encoding="utf-8"))
    if DOWNLOAD_LIMIT and DOWNLOAD_LIMIT > 0:
        links = links[:DOWNLOAD_LIMIT]

    out_dir.mkdir(parents=True, exist_ok=True)

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1', 
        'Referer': 'https://www.google.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none', 
        'Sec-Fetch-User': '?1',
    }

    valid = {}
    total = len(links)

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, url in enumerate(links, start=1):
        print(f"[{i}/{total}] fetching: {url}")
        fname, err = download_one(url, out_dir, session)
        if fname:
            valid[url] = fname
            print(f"  -> saved as {fname}")
        else:
            print(f"  -> skipped ({err})")
        time.sleep(REQUEST_SLEEP)

    # save valid_links.json
    with valid_links_file.open("w", encoding="utf-8") as fh:
        json.dump(valid, fh, indent=2, ensure_ascii=False)

    print(f"Finished. {len(valid)} valid pages saved to {out_dir}. Mapping in {valid_links_file}")


if __name__ == "__main__":
    main()
