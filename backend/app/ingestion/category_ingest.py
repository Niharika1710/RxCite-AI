"""
Category-based ingestion: pulls FDA labels by therapeutic class or
indication instead of by hand-typed drug name, with pagination.

This is what makes the knowledge base scalable — adding a whole drug
class is a config change, not fifteen more strings in a list.
"""
import json
import os
import time
import requests

from app.ingestion.fda_ingest import (
    RAW_DATA_DIR,
    normalize_drug_label,
    FDA_BASE_URL,
)

PAGE_SIZE = 100          # openFDA allows up to 1000; 100 keeps requests light
MAX_PAGES = 10           # safety cap so a broad query can't run away
REQUEST_PAUSE = 0.3      # be polite to the shared (keyless) rate limit


# Ready-made categories. Each value is an openFDA search expression.
CATEGORIES = {
    "nsaids": 'openfda.pharm_class_epc:"Nonsteroidal Anti-inflammatory Drug"',
    "beta_blockers": 'openfda.pharm_class_epc:"beta-Adrenergic Blocker"',
    "ace_inhibitors": 'openfda.pharm_class_epc:"Angiotensin Converting Enzyme Inhibitor"',
    "statins": 'openfda.pharm_class_epc:"HMG-CoA Reductase Inhibitor"',
    "ssri": 'openfda.pharm_class_epc:"Selective Serotonin Reuptake Inhibitor"',
    "antibiotics_macrolide": 'openfda.pharm_class_epc:"Macrolide Antimicrobial"',
    # Indication-driven rather than class-driven:
    "diabetes": 'indications_and_usage:"type 2 diabetes"',
    "hypertension": 'indications_and_usage:"hypertension"',
}


def fetch_page(search_expr: str, skip: int, limit: int = PAGE_SIZE) -> dict:
    """Fetch one page of labels matching a search expression."""
    params = {"search": search_expr, "limit": limit, "skip": skip}
    response = requests.get(FDA_BASE_URL, params=params, timeout=30)
    if response.status_code == 404:
        return {"results": []}      # openFDA returns 404 when a page is empty
    response.raise_for_status()
    return response.json()


def label_identity(label: dict) -> str | None:
    """Pick a stable name for a label so we can deduplicate across pages."""
    openfda = label.get("openfda", {})
    for field in ("generic_name", "substance_name", "brand_name"):
        values = openfda.get(field)
        if values:
            return values[0].lower().strip()
    return None


def fetch_category(category_key: str, max_pages: int = MAX_PAGES) -> list[dict]:
    """
    Page through every label in a category, deduplicated by drug name.
    Returns a list of {name, label} dicts.
    """
    if category_key not in CATEGORIES:
        raise ValueError(f"Unknown category '{category_key}'. Options: {list(CATEGORIES)}")

    search_expr = CATEGORIES[category_key]
    seen: set[str] = set()
    collected: list[dict] = []

    for page in range(max_pages):
        skip = page * PAGE_SIZE
        print(f"  page {page + 1} (skip={skip})...", end=" ")
        data = fetch_page(search_expr, skip)
        results = data.get("results", [])

        if not results:
            print("no more results")
            break

        new_on_page = 0
        for label in results:
            name = label_identity(label)
            if not name or name in seen:
                continue
            seen.add(name)
            collected.append({"name": name, "label": label})
            new_on_page += 1

        print(f"{len(results)} labels, {new_on_page} new drugs")
        time.sleep(REQUEST_PAUSE)

    return collected


def save_category_raw(category_key: str, items: list[dict]) -> str:
    """Persist the raw pull so we don't re-hit the API on every run."""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    path = os.path.join(RAW_DATA_DIR, f"_category_{category_key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    return path


def category_to_documents(category_key: str, max_pages: int = MAX_PAGES) -> list[dict]:
    """
    Full pipeline for one category: fetch -> save raw -> normalize -> chunk.
    Returns chunk documents ready for embedding.
    """
    print(f"Fetching category: {category_key}")
    items = fetch_category(category_key, max_pages=max_pages)
    print(f"  -> {len(items)} unique drugs")

    path = save_category_raw(category_key, items)
    print(f"  -> raw saved to {path}")

    documents: list[dict] = []
    for item in items:
        # normalize_drug_label expects the same shape the single-drug fetch returns
        docs = normalize_drug_label(item["name"], {"results": [item["label"]]})
        documents.extend(docs)

    print(f"  -> {len(documents)} chunks")
    return documents


if __name__ == "__main__":
    import sys

    key = sys.argv[1] if len(sys.argv) > 1 else "nsaids"
    docs = category_to_documents(key, max_pages=2)   # 2 pages while testing

    print(f"\nTotal chunks for '{key}': {len(docs)}")
    if docs:
        print("\nSample chunk:")
        print({k: (v[:80] + "..." if k == "text" else v) for k, v in docs[0].items()})