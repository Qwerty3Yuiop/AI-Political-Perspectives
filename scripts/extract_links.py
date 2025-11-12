#!/usr/bin/env python3
"""Extract AllSides story links from wayback HTML files into data/links.json.

This script scans files under data/wayback_raw for anchor hrefs of the
form `/web/<timestamp>/https://www.allsides.com/story/...` and extracts the
https://www.allsides.com/story/... portion, deduplicates, and writes a
JSON array to data/links.json.

Usage: python3 scripts/extract_links.py
"""

import json
import os
import re
from pathlib import Path


def find_links_in_text(text):
	"""Return a list of matching AllSides story links found in the HTML text.

	Matches href attributes like:
	  href="/web/20220521190216/https://www.allsides.com/story/slug-here"
	and returns the https://... portion.
	"""
	pattern = re.compile(
		r'href=["\']\/web\/\d+\/(https:\/\/www\.allsides\.com\/story\/[^"\'\s>]+)',
		re.IGNORECASE,
	)
	return pattern.findall(text)


def main():
	repo_root = Path(__file__).resolve().parents[1]
	wayback_dir = repo_root / "data" / "wayback_raw"
	out_file = repo_root / "data" / "links.json"

	if not wayback_dir.exists():
		print(f"Wayback directory not found: {wayback_dir}")
		return

	links = set()

	for root, _, files in os.walk(wayback_dir):
		for fname in files:
			if not fname.lower().endswith(".html"):
				continue
			fpath = Path(root) / fname
			try:
				text = fpath.read_text(encoding="utf-8", errors="replace")
			except Exception as e:
				print(f"Failed to read {fpath}: {e}")
				continue
			matches = find_links_in_text(text)
			for m in matches:
				links.add(m)

	links_list = sorted(links)
	out_file.parent.mkdir(parents=True, exist_ok=True)
	with out_file.open("w", encoding="utf-8") as fh:
		json.dump(links_list, fh, indent=2, ensure_ascii=False)

	print(f"Wrote {len(links_list)} unique links to {out_file}")


if __name__ == "__main__":
	main()

