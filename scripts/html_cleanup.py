#!/usr/bin/env python3
"""
Clean roundups_raw HTML files by extracting the section starting at
"Summary from the AllSides News Team" through the end of the file.

Usage examples:
  python3 scripts/html_cleanup.py --input-file data/roundups_raw/facing-retaliation-taliban-first-afghan-evacuees-arrive-us.html --output-dir data/roundups_cleaned
  python3 scripts/html_cleanup.py --input-dir data/roundups_raw --output-dir data/roundups_cleaned

The script is intentionally dependency-free and uses simple substring/regex
heuristics because all files follow the same AllSides roundup structure.
"""

from pathlib import Path
import re
import json
import shutil
import tempfile
import os


def extract_summary_section(html_text: str) -> tuple[str, bool]:
	"""Return (section_text, found_marker).

	The boolean indicates whether the extractor found an explicit marker
	(or a heading containing "Summary"). If False the returned section is
	a fallback (last ~8KB) and should be treated as "not found" for
	automation purposes.
 
 	Heuristics tried in order:
	1. Find the literal phrase "Summary from the AllSides News Team" and
	   include the nearest opening '<' before it (so we capture the heading tag).
	2. Fallback: look for an <h[1-6]> that contains the word "Summary".
	3. Final fallback: return the last chunk of the file (safe default) and
	   mark found=False.
	"""
	marker = "Summary from the AllSides News Team"
	idx = html_text.find(marker)
	if idx != -1:
		# include the opening tag for the heading if present
		start = html_text.rfind('<', 0, idx)
		if start == -1:
			start = idx
			return (html_text[start:], True)
		return (html_text[start:], True)

	# fallback: find an <h1>-<h6> containing the word Summary (lenient)
	m = re.search(r"<h[1-6][^>]*>\s*[^<]{0,120}?Summary[^<]{0,120}?</h[1-6]>", html_text, re.IGNORECASE)
	if m:
		start = html_text.rfind('<', 0, m.start())
		if start == -1:
			start = m.start()
		return (html_text[start:], True)

	# last-resort fallback: return the last ~8KB of the file (should include bottom portion)
	return (html_text[-8192:], False)


def _atomic_write(path: Path, text: str) -> None:
	"""Write text to path atomically by writing to a temp file then renaming."""
	dirpath = path.parent
	dirpath.mkdir(parents=True, exist_ok=True)
	fd, tmp = tempfile.mkstemp(dir=str(dirpath))
	try:
		with os.fdopen(fd, 'w', encoding='utf-8') as fh:
			fh.write(text)
		os.replace(tmp, str(path))
	finally:
		if os.path.exists(tmp):
			try:
				os.remove(tmp)
			except Exception:
				pass


def remove_valid_link_for_filename(filename: str, valid_links_path: Path, verbose: bool = False) -> int:
	"""Remove entries from valid_links.json whose value equals filename.

	Returns the number of removed entries.
	"""
	if not valid_links_path.exists():
		if verbose:
			print(f"[WARN] valid_links.json not found at {valid_links_path}")
		return 0

	try:
		data = json.loads(valid_links_path.read_text(encoding='utf-8'))
	except Exception as e:
		if verbose:
			print(f"[ERROR] Failed to read valid_links.json: {e}")
		return 0

	keys_to_remove = [k for k, v in data.items() if v == filename]
	for k in keys_to_remove:
		del data[k]

	if keys_to_remove:
		try:
			valid_links_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
			if verbose:
				print(f"Removed {len(keys_to_remove)} entries from {valid_links_path} for file {filename}")
		except Exception as e:
			if verbose:
				print(f"[ERROR] Failed to write valid_links.json: {e}")
	else:
		if verbose:
			print(f"No entries found in {valid_links_path} for file {filename}")

	return len(keys_to_remove)


def process_file_inplace(input_path: Path, review_dir: Path, valid_links_path: Path, dry_run: bool = False, verbose: bool = False) -> bool:
	"""Process a single file in place.

	If marker is found: overwrite original file with cleaned section.
	If marker is not found: move file to review_dir and remove mapping from valid_links.json.
	"""
	html = input_path.read_text(encoding='utf-8', errors='replace')
	section, found = extract_summary_section(html)

	if found:
		if dry_run:
			if verbose:
				print(f"[DRY-RUN] Would overwrite {input_path} with cleaned section ({len(section)} bytes)")
			return True

		# atomic overwrite
		_atomic_write(input_path, section)
		if verbose:
			print(f"Overwrote {input_path} with cleaned section ({len(section)} bytes)")
		return True

	# not found: move to review folder and update valid_links
	review_dir.mkdir(parents=True, exist_ok=True)
	target = review_dir / input_path.name
	if dry_run:
		if verbose:
			print(f"[DRY-RUN] Would move {input_path} -> {target} and remove from valid_links.json")
		return False

	try:
		shutil.move(str(input_path), str(target))
		if verbose:
			print(f"Moved {input_path} -> {target} (marker not found)")
	except Exception as e:
		if verbose:
			print(f"[ERROR] Failed to move {input_path} to review folder: {e}")
		return False

	remove_valid_link_for_filename(input_path.name, valid_links_path, verbose=verbose)
	return False


# Configuration: edit these variables instead of using CLI/argparse
# Set either INPUT_FILE (single Path) or INPUT_DIR (directory with .html files).
INPUT_DIR: Path | None = Path("data/roundups_raw")
INPUT_FILE: Path | None = None
# For in-place operation we don't write to an output dir; keep OUTPUT_DIR for compatibility if needed
OUTPUT_DIR: Path = Path("data/roundups_cleaned")
DRY_RUN: bool = False
VERBOSE: bool = True
# Where to move files that need human review (marker missing)
REVIEW_DIR: Path = Path("data/roundups_review")
# Path to the valid links JSON mapping (url -> filename)
VALID_LINKS_PATH: Path = Path("data/valid_links.json")


def run() -> int:
	# collect files
	if INPUT_FILE:
		files = [INPUT_FILE]
	else:
		if not INPUT_DIR:
			print("No input directory or file configured.")
			return 2
		files = sorted([p for p in INPUT_DIR.iterdir() if p.suffix.lower() == ".html"])

	if not files:
		print("No HTML files found to process.")
		return 2

	succeeded = 0
	failures = 0
	for f in files:
		ok = process_file_inplace(f, REVIEW_DIR, VALID_LINKS_PATH, dry_run=DRY_RUN, verbose=VERBOSE)
		if ok:
			succeeded += 1
		else:
			failures += 1

	if VERBOSE:
		print(f"Processed {len(files)} file(s). Overwritten: {succeeded}. Moved for review: {failures}.")

	return 0


if __name__ == "__main__":
	raise SystemExit(run())

