"""
Academic Paper Finder
----------------------
Searches a topic/project name (e.g. "hand gesture system for deaf and
hard-of-hearing people") across free academic metadata APIs and returns
matching journal / conference papers, including IEEE-published ones.

IMPORTANT NOTE ON IEEE:
IEEE Xplore does not allow direct scraping of ieeexplore.ieee.org (it's
blocked by their ToS and bot protection). Instead this script uses:
  - Semantic Scholar API  (free, no key needed)
  - CrossRef API          (free, no key needed)
  - arXiv API             (free, no key needed)
These APIs index metadata for IEEE-published papers too, so you can find
and filter them (see filter_ieee) without violating IEEE's terms.

If you have an official IEEE Xplore API key (free to request at
https://developer.ieee.org), you can add a search_ieee_official() function
using their REST endpoint — happy to add that if you get a key.

Usage:
    python paper_scraper.py "hand gesture recognition for deaf people"
    (or just run it and type the topic when prompted)
"""

import argparse
import csv
import time
import xml.etree.ElementTree as ET

import requests


def request_with_retry(url, params, max_retries=5, base_delay=5, timeout=15):
    """
    GET request that automatically waits and retries on 429 (rate limit)
    and transient 5xx errors, using exponential backoff.
    """
    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 429:
            # Respect Retry-After header if the server sends one, else back off
            wait = int(r.headers.get("Retry-After", base_delay * (2 ** attempt)))
            print(f"  Rate limited (429). Waiting {wait}s before retry "
                  f"({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        if r.status_code >= 500:
            wait = base_delay * (2 ** attempt)
            print(f"  Server error {r.status_code}. Waiting {wait}s before retry "
                  f"({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"Gave up after {max_retries} retries for {url}")


def search_semantic_scholar(topic, limit=25):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": topic,
        "limit": limit,
        "fields": "title,authors,year,venue,externalIds,url",
    }
    results = []
    try:
        r = request_with_retry(url, params)
        for paper in r.json().get("data", []):
            results.append({
                "source": "Semantic Scholar",
                "title": paper.get("title") or "",
                "authors": ", ".join(a.get("name", "") for a in paper.get("authors", [])),
                "year": paper.get("year") or "",
                "venue": paper.get("venue") or "",
                "doi": (paper.get("externalIds") or {}).get("DOI", ""),
                "url": paper.get("url") or "",
            })
    except Exception as e:
        print(f"[Semantic Scholar] Error: {e}")
    return results


def search_crossref(topic, rows=25):
    url = "https://api.crossref.org/works"
    params = {"query": topic, "rows": rows}
    results = []
    try:
        r = request_with_retry(url, params)
        for item in r.json().get("message", {}).get("items", []):
            title = item.get("title", [""])
            title = title[0] if title else ""
            authors = ", ".join(
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            ) if item.get("author") else ""
            year = None
            for key in ("published-print", "published-online", "published"):
                parts = item.get(key, {}).get("date-parts")
                if parts and parts[0] and parts[0][0]:
                    year = parts[0][0]
                    break
            venue = item.get("container-title", [""])
            venue = venue[0] if venue else ""
            results.append({
                "source": "CrossRef",
                "title": title,
                "authors": authors,
                "year": year or "",
                "venue": venue,
                "doi": item.get("DOI", ""),
                "url": item.get("URL", ""),
            })
    except Exception as e:
        print(f"[CrossRef] Error: {e}")
    return results


def search_arxiv(topic, max_results=25):
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{topic}", "start": 0, "max_results": max_results}
    results = []
    try:
        r = request_with_retry(url, params)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.content)
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            authors = ", ".join(
                a.find("atom:name", ns).text
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            )
            pub_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)
            results.append({
                "source": "arXiv",
                "title": (title_el.text or "").strip().replace("\n", " ") if title_el is not None else "",
                "authors": authors,
                "year": pub_el.text[:4] if pub_el is not None else "",
                "venue": "arXiv preprint",
                "doi": "",
                "url": id_el.text if id_el is not None else "",
            })
    except Exception as e:
        print(f"[arXiv] Error: {e}")
    return results


def filter_ieee(results):
    """Keep only results whose venue/journal name mentions IEEE."""
    return [r for r in results if r.get("venue") and "ieee" in r["venue"].lower()]


def dedupe(results):
    seen = set()
    unique = []
    for r in results:
        key = (r["title"].strip().lower(), r.get("doi", ""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def save_to_csv(results, filename):
    if not results:
        print(f"No results to save for {filename}")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "title", "authors", "year", "venue", "doi", "url"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved {len(results)} results -> {filename}")


def main():
    parser = argparse.ArgumentParser(description="Search academic APIs for papers on a topic/project name.")
    parser.add_argument("topic", nargs="*", help="Topic or project name to search for")
    args = parser.parse_args()

    topic = " ".join(args.topic).strip() if args.topic else input("Enter project/topic name: ").strip()
    if not topic:
        print("No topic provided, exiting.")
        return

    print(f"\nSearching for: {topic}\n")

    all_results = []
    print("Querying Semantic Scholar...")
    all_results += search_semantic_scholar(topic)
    time.sleep(1)

    print("Querying CrossRef...")
    all_results += search_crossref(topic)
    time.sleep(1)

    print("Querying arXiv...")
    all_results += search_arxiv(topic)

    all_results = dedupe(all_results)
    ieee_results = filter_ieee(all_results)

    print(f"\nTotal unique results: {len(all_results)}")
    print(f"IEEE-venue results: {len(ieee_results)}")

    save_to_csv(all_results, "all_papers.csv")
    save_to_csv(ieee_results, "ieee_papers.csv")


if __name__ == "__main__":
    main()