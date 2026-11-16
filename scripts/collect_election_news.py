"""Collect public HTML/JSON-LD news, with provenance; no paywall bypass.

Run from PyCharm or: python3 scripts/collect_election_news.py
Requires Beautiful Soup (requirements-data.txt) and the system curl executable.
"""

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "election_2026"
START, END = "2026-11-03", "2026-11-16"
SEEDS = [
    "https://www.cbsnews.com/live-updates/election-day-2026-midterms/",
    "https://www.cbsnews.com/live-updates/house-election-results-2026/",
    "https://www.cbsnews.com/live-updates/senate-election-results-2026/",
    "https://www.cbsnews.com/news/republican-losses-roil-gop-midterms-vance-cruz-desantis/",
    "https://www.cbsnews.com/news/leading-dem-on-midterms-aftermath-were-still-in-the-fight-of-our-lives/",
    "https://www.theguardian.com/us-news/2026/nov/04/democrats-house-midterm-elections-results",
    "https://www.theguardian.com/us-news/2026/nov/03/midterm-voters-republican-democrats-trump-second-term",
    "https://theprint.in/world/democrats-seize-congress-in-sweeping-midterm-repudiation-of-trump/3090089/",
    "https://theprint.in/world/democrats-flex-congressional-majorities-as-trump-accepts-electoral-losses/3090972/",
    "https://www.investing.com/news/politics-news/how-democrats-won-their-blowout-midterm-victory-5009828",
    "https://www.axios.com/2026/11/03/election-day-midterm-trump-democrats-republicans",
    "https://rollcall.com/2026/11/03/key-midterm-election-results/",
    "https://www.ap.org/news-highlights/elections/2026/trump-backed-republican-redistricting-sought-a-midterm-edge-it-didnt-work/",
]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ld = []
        self.links = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._script = []
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            try:
                self.ld.append(json.loads("".join(self._script)))
            except json.JSONDecodeError:
                pass
            self._script = None


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "figure", "iframe"):
            self.ignore += 1
        if not self.ignore and tag in ("p", "div", "li", "br", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "figure", "iframe"):
            self.ignore = max(0, self.ignore - 1)
        if not self.ignore and tag in ("p", "div", "li", "h2", "h3"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def clean_body(value):
    parser = BodyParser()
    parser.feed(value)
    text = "".join(parser.parts).replace("\xa0", " ")
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in text.splitlines()]
    paragraphs = [p for p in paragraphs if p and not re.match(
        r"^(Read (?:the )?(?:full|more)|Watch (?:the|live)|More from CBS|By\s+[A-Z].{0,50}$)", p
    )]
    return "\n\n".join(paragraphs).strip()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def normalized(text):
    return re.sub(r"\W+", " ", text.lower()).strip()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def public_html_article(page, url):
    """Extract only observed, publisher-specific body containers in public HTML."""
    selectors = {
        "www.theguardian.com": ".article-body-commercial-selector > p",
        "rollcall.com": "article .font-lyon > p",
        "www.ap.org": "article .content-container__inner > p",
    }
    selector = selectors.get(urlsplit(url).netloc)
    if not selector:
        return None
    soup = BeautifulSoup(page, "html.parser")
    paragraphs = soup.select(selector)
    date = soup.select_one('meta[property="article:published_time"]')
    title = soup.select_one('meta[property="og:title"]')
    if not paragraphs or not date or not title:
        return None
    return {"@type": "NewsArticle", "headline": title.get("content", ""),
            "datePublished": date.get("content", ""), "url": url,
            "articleBody": "".join(str(p) for p in paragraphs),
            "extraction_method": "public HTML body selector: " + selector}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url):
    key = sha(url)[:20]
    path = BASE / "raw" / (key + ".html")
    meta = path.with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and meta.exists():
        info = json.loads(meta.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8", errors="replace"), info
    result = subprocess.run([
        "curl", "-L", "--max-time", "40", "--retry", "1", "-sS",
        "--user-agent", "ID2222-course-corpus/1.0 (educational text-similarity experiment)",
        "-o", str(path), "-w", "%{http_code}\n%{url_effective}", url,
    ], capture_output=True, text=True)
    output = result.stdout.splitlines()
    info = {"url": url, "http_status": output[0] if output else "000",
            "final_url": output[1] if len(output) > 1 else url,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "curl_exit": result.returncode, "error": result.stderr[:300]}
    save_json(meta, info)
    time.sleep(0.35)
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else "", info


def collect(max_pages=65):
    queue = list(SEEDS)
    seen_urls, seen_bodies, records, audit = set(), {}, [], []
    while queue and len(seen_urls) < max_pages:
        url = queue.pop(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        page, info = fetch(url)
        log = dict(info, accepted=0, rejected={})
        audit.append(log)
        if info["http_status"] != "200":
            print("SKIP HTTP", info["http_status"], url, flush=True)
            continue
        parser = PageParser()
        parser.feed(page)
        objects = [o for root in parser.ld for o in walk(root)]
        # Do not extract article bodies from explicitly paywalled pages.
        if any(o.get("isAccessibleForFree") in (False, "False", "false") for o in objects):
            log["rejected"]["paywall"] = 1
            continue
        if not any(o.get("articleBody") for o in objects):
            html_article = public_html_article(page, url)
            if html_article:
                objects.append(html_article)
        if re.search(r"<title>Just a moment", page, re.I):
            log["rejected"]["access_challenge"] = 1
        for obj in objects:
            body = obj.get("articleBody")
            if not isinstance(body, str):
                continue
            title = obj.get("headline", obj.get("name", ""))
            published = obj.get("datePublished", "")
            text = clean_body(body)
            reason = None
            if not (START <= published[:10] <= END):
                reason = "outside_event_dates"
            elif len(text.split()) < 80:
                reason = "under_80_words"
            elif not re.search(r"\b(election|midterm|senate|congress|ballot|voter|redistrict|democrat|republican)", title + " " + text, re.I):
                reason = "not_election_related"
            if reason:
                log["rejected"][reason] = log["rejected"].get(reason, 0) + 1
                continue
            checksum = sha(normalized(text))
            article_url = obj.get("url") or url
            if not isinstance(article_url, str):
                article_url = url
            article_url = urljoin(url, article_url)
            if checksum in seen_bodies:
                seen_bodies[checksum]["duplicate_source_urls"].append(article_url)
                log["rejected"]["duplicate_body"] = log["rejected"].get("duplicate_body", 0) + 1
                continue
            doc_id = "real_" + sha(article_url + checksum)[:14]
            file = BASE / "originals" / (doc_id + ".txt")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text + "\n", encoding="utf-8")
            record = {"id": doc_id, "kind": "real", "title": title,
                      "document_type": "live_update" if obj.get("@type") == "BlogPosting" else "article",
                      "publisher_domain": urlsplit(url).netloc, "source_url": article_url,
                      "page_url": url, "published_at": published,
                      "modified_at": obj.get("dateModified"),
                      "authors": [a.get("name", "") for a in walk(obj.get("author", [])) if a.get("name")],
                      "retrieved_at_utc": info["fetched_at_utc"],
                      "path": str(file.relative_to(ROOT)), "word_count": len(text.split()),
                      "sha256": sha(text + "\n"), "normalized_sha256": checksum,
                      "raw_html": str((BASE / "raw" / (sha(url)[:20] + ".html")).relative_to(ROOT)),
                      "license": "Publisher copyright; no redistribution permission inferred",
                      "extraction": obj.get("extraction_method", "JSON-LD articleBody") + "; HTML/figures and standalone read-more lines removed; title excluded",
                      "duplicate_source_urls": []}
            records.append(record)
            seen_bodies[checksum] = record
            log["accepted"] += 1
        # Follow only observed news links from the event pages, not arbitrary URLs.
        if urlsplit(url).netloc == "www.cbsnews.com":
            links = list(parser.links)
            for obj in objects:
                if isinstance(obj.get("articleBody"), str):
                    links.extend(re.findall(r'data-href="([^"]+)"', obj["articleBody"]))
            for link in links:
                target = canonical(urljoin(url, link))
                if urlsplit(target).netloc != "www.cbsnews.com":
                    continue
                if "/news/" not in target:
                    continue
                if not re.search(r"election|midterm|republican|democrat|senate|house-seat|redistrict|congress", target):
                    continue
                if target not in seen_urls and target not in queue:
                    queue.append(target)
        save_json(BASE / "sources.json", records)
        save_json(BASE / "collection_audit.json", audit)
        print("COLLECT", len(seen_urls), "pages;", len(records), "unique documents; +", log["accepted"], url, flush=True)
    save_json(BASE / "sources.json", records)
    save_json(BASE / "collection_audit.json", audit)
    print("DONE", len(records), "real documents", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=65)
    collect(parser.parse_args().max_pages)
