"""wayback_scraper.py

Fetch Wayback capture metadata via the CDX API, construct the raw HTML link for 
each capture, and download the content into a local directory.

Configuration is hardcoded in the main() function.
"""
import os
import re
import time
import json
import hashlib
from typing import List, Optional

import requests

BASE = 'https://web.archive.org'
CDX_API_BASE = 'https://web.archive.org/cdx/search/cdx'
DEFAULT_URL_PATTERN = 'https://www.allsides.com/headline-roundup*'

# Standard headers to simulate a common browser and avoid unnecessary rate limiting
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
    'Accept': '*/*', # Accept any content type for the API call
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.google.com/',
}


def fetch_archives_via_cdx(url_pattern: str, session: requests.Session) -> List[str]:
    print(f"Querying CDX API for: {url_pattern}")
    
    params = {
        'url': url_pattern,
        'output': 'json',
        'limit': ''
    }
    
    try:
        r = session.get(CDX_API_BASE, params=params, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error querying CDX API: {e}")
        return []

    try:
        data = r.json()
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from CDX API: {e}")
        print("Raw response may be malformed. Check the CDX API URL and parameters.")
        return []

    if not data or len(data) <= 1:
        return []

    hrefs: List[str] = []

    for row in data[1:]:
        timestamp = row[1]
        original_url = row[2]
        status_code = row[4]

        if status_code != '200':
            continue

        if len(timestamp) >= 14 and original_url:
            wayback_path = f'/web/{timestamp}/{original_url}'
            hrefs.append(wayback_path)
        
    return hrefs


def download_archives(hrefs: List[str], outdir: str, delay: float = 1.0, limit: Optional[int] = None) -> None:
    """
    Downloads the raw HTML content for a list of Wayback paths.
    
    Uses the 'im_' prefix to request raw content, which is often more successful 
    than 'id_' at stripping the JavaScript frame.
    """
    os.makedirs(outdir, exist_ok=True)

    with requests.Session() as session:
        session.headers.update(HEADERS)

        total_to_download = len(hrefs)
        if limit is not None:
             hrefs = hrefs[:limit]
             total_to_download = limit

        for i, href_str in enumerate(hrefs):

            # 1. Modify the path to request RAW HTML using the 'im_' prefix
            if href_str.startswith('/web/'):
                 full_download_url = BASE + href_str
            else:
                print(f"Skipping malformed href: {href_str}")
                continue

            print(f"[{i+1}/{total_to_download}] Downloading raw: {full_download_url}")

            try:
                # 2. Fetch the raw content
                r = session.get(full_download_url, timeout=30)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"Failed to download {full_download_url}: {e}")
                continue
            
            # 3. Generate a safe and unique filename
            # Extract the 14-digit timestamp from the original path
            m = re.search(r'/web/(\d{14})/', href_str) 
            ts = m.group(1) if m else str(int(time.time()))
            
            # Use a short MD5 hash of the original target URL for uniqueness
            # The original URL is the part after the timestamp in the href
            original_url_match = re.search(r'/web/\d{14}/(.*)', href_str)
            original_url = original_url_match.group(1) if original_url_match else href_str
            safe_hash = hashlib.md5(original_url.encode('utf-8')).hexdigest()[:8]
            
            fname = f"{ts}_{safe_hash}.html"
            path = os.path.join(outdir, fname)
            
            try:
                # 4. Save the raw content in binary mode ('wb') for integrity
                with open(path, 'wb') as fh: 
                    fh.write(r.content)
                print(f"Saved: {path}")
            except IOError as e:
                print(f"Error saving {path}: {e}")

            time.sleep(delay)


def main() -> None:
    # --- CONFIGURATION ---
    # The URL pattern to query the Wayback Machine CDX API for
    URL_PATTERN = DEFAULT_URL_PATTERN 
    # The directory where HTML files will be saved
    OUT_DIR = 'Data/wayback_raw'
    # Maximum number of pages to download (set to None for no limit)
    DOWNLOAD_LIMIT = None
    # Delay (in seconds) between each individual download request
    DOWNLOAD_DELAY = 1.0
    # -------------------------------
    
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        hrefs = fetch_archives_via_cdx(URL_PATTERN, session)
        
        if not hrefs:
            print("No archive links found via CDX API. Check the URL pattern or try again later.")
            return

        print(f"Found {len(hrefs)} archive links (downloading up to {DOWNLOAD_LIMIT or 'all'}).")
        download_archives(
            hrefs, 
            OUT_DIR, 
            delay=DOWNLOAD_DELAY, 
            limit=DOWNLOAD_LIMIT
        )


if __name__ == '__main__':
    main()