"""
Ingests all Stripe Singapore legal documents into a single TF-IDF search index.

Two modes:
  1. From the web (no PDFs needed):
       python ingest.py --web

  2. From local PDFs:
       python ingest.py docs/ssa.pdf docs/connect.pdf ...

Output: store.pkl  (chunks + sources + fitted TF-IDF matrix, used by retrieval.py)
"""

import sys
import re
import pickle
import argparse
import urllib.request
from html.parser import HTMLParser

from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
OUTPUT_PATH = "store.pkl"

STRIPE_SG_DOCS = {
    "Services Agreement":          "https://stripe.com/en-sg/legal/ssa",
    "Connected Account Agreement": "https://stripe.com/en-sg/legal/connect-account",
    "Consumer Terms":              "https://stripe.com/en-sg/legal/consumer",
    "Partner Ecosystem":           "https://stripe.com/en-sg/legal/partner-ecosystem",
    "App Developer Agreement":     "https://stripe.com/en-sg/legal/app-developer-agreement",
    "Privacy Policy":              "https://stripe.com/en-sg/privacy",
    "IP Policy":                   "https://stripe.com/en-sg/legal/ip-policy",
    "Climate Contribution Terms":  "https://stripe.com/en-sg/legal/climate-contributions",
    "Atlas Terms":                 "https://stripe.com/en-sg/legal/atlas",
    "Restricted Businesses":       "https://stripe.com/en-sg/legal/restricted-businesses",
    "Licenses":                    "https://stripe.com/en-sg/spc/licenses",
}


# ── HTML stripping ────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_pdf(path: str) -> str:
    if not HAS_PDF:
        raise RuntimeError("pypdf not installed: pip install pypdf")
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, source_label: str) -> list[dict]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append({
            "text": " ".join(words[i : i + CHUNK_SIZE]),
            "source": source_label,
        })
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Local context files ───────────────────────────────────────────────────────

LOCAL_DATA_DIR = "data"

LOCAL_DATA_LABELS = {
    "company_profile.txt":      "NexaPay Company Profile",
    "compliance_procedures.txt": "NexaPay Compliance Procedures",
    "past_qa.txt":              "NexaPay Past Q&A",
}

def ingest_local_data() -> list[dict]:
    import os
    all_chunks = []
    for filename, label in LOCAL_DATA_LABELS.items():
        path = os.path.join(LOCAL_DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"  ✗ Not found: {path}")
            continue
        print(f"  Loading: {label} ...")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_text(text, source_label=label)
        all_chunks.extend(chunks)
        print(f"    → {len(chunks)} chunks")
    return all_chunks


# ── Ingest sources ────────────────────────────────────────────────────────────

def ingest_web() -> list[dict]:
    all_chunks = []
    for name, url in STRIPE_SG_DOCS.items():
        print(f"  Fetching: {name} ...")
        try:
            text = fetch_url(url)
            chunks = chunk_text(text, source_label=name)
            all_chunks.extend(chunks)
            print(f"    → {len(chunks)} chunks")
        except Exception as e:
            print(f"    ✗ Failed ({e})")
    return all_chunks


def ingest_pdfs(paths: list[str]) -> list[dict]:
    all_chunks = []
    for path in paths:
        print(f"  Reading: {path} ...")
        text = extract_pdf(path)
        label = path.split("/")[-1].replace(".pdf", "")
        chunks = chunk_text(text, source_label=label)
        all_chunks.extend(chunks)
        print(f"    → {len(chunks)} chunks")
    return all_chunks


# ── Build TF-IDF index and save ───────────────────────────────────────────────

def build_and_save(chunks: list[dict]):
    texts = [c["text"] for c in chunks]
    sources = [c["source"] for c in chunks]

    print(f"\nBuilding TF-IDF index over {len(texts)} chunks...")
    vectorizer = TfidfVectorizer(stop_words="english", max_features=50_000)
    matrix = vectorizer.fit_transform(texts)

    with open(OUTPUT_PATH, "wb") as f:
        pickle.dump({
            "chunks": texts,
            "sources": sources,
            "vectorizer": vectorizer,
            "matrix": matrix,
        }, f)

    print(f"Saved to {OUTPUT_PATH}. Ready to run the API.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", action="store_true",
                        help="Fetch all 11 Stripe SG legal docs from the web")
    parser.add_argument("pdfs", nargs="*",
                        help="One or more local PDF paths")
    args = parser.parse_args()

    if args.web:
        print("Fetching all Stripe Singapore legal documents...\n")
        chunks = ingest_web()
    elif args.pdfs:
        chunks = ingest_pdfs(args.pdfs)
    else:
        print("Usage:\n  python ingest.py --web\n  python ingest.py file1.pdf ...")
        sys.exit(1)

    print("\nLoading NexaPay internal context files...\n")
    chunks += ingest_local_data()

    build_and_save(chunks)
