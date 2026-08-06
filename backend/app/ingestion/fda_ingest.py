"""
Pulls drug label data from the openFDA API and saves raw JSON to disk.
No API key required for this volume of requests.
"""
import json
import os
import time
import requests

FDA_BASE_URL = "https://api.fda.gov/drug/label.json"
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw_fda")

# Our small demo set — chosen to cover different risk profiles
DRUG_NAMES = [
    "ibuprofen",
    "metformin",
    "warfarin",
    "acetaminophen",   # paracetamol
    "aspirin",
    "amoxicillin",
    "atorvastatin",
    "lisinopril",
    "omeprazole",
    "azithromycin",
    "amlodipine",
    "sertraline",
    "gabapentin",
    "prednisone",
    "ciprofloxacin",
]

def fetch_label(drug_name: str) -> dict:
    """Fetch the FDA label for a single drug by generic name."""
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1,
    }
    response = requests.get(FDA_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def save_raw(drug_name: str, data: dict) -> str:
    """Save the raw JSON response to data/raw_fda/<drug_name>.json"""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    filepath = os.path.join(RAW_DATA_DIR, f"{drug_name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return filepath


def ingest_all():
    """Fetch and save labels for all drugs in DRUG_NAMES."""
    results = []
    for drug in DRUG_NAMES:
        print(f"Fetching label for: {drug}")
        try:
            data = fetch_label(drug)
            filepath = save_raw(drug, data)
            print(f"  Saved to: {filepath}")
            results.append({"drug": drug, "status": "success", "path": filepath})
        except requests.exceptions.HTTPError as e:
            print(f"  FAILED: {e}")
            results.append({"drug": drug, "status": "failed", "error": str(e)})
        time.sleep(1)  # be polite to the API, no key means shared rate limit
    return results



# --- Normalization & Chunking ---

# The FDA label sections we care about, in priority order.
# Each becomes its own labeled chunk (or set of chunks if long).
RELEVANT_SECTIONS = [
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "contraindications",
    "warnings_and_cautions",
    "warnings",
    "precautions",
    "pregnancy",
    "nursing_mothers",
    "pediatric_use",
    "geriatric_use",
    "drug_interactions",
    "adverse_reactions",
    "overdosage",
]

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 100    # overlap so we don't cut a sentence's meaning in half


def load_raw(drug_name: str) -> dict:
    """Load a previously saved raw FDA JSON file."""
    filepath = os.path.join(RAW_DATA_DIR, f"{drug_name}.json")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def simple_chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split long text into overlapping chunks by character count."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def normalize_drug_label(drug_name: str, raw_data: dict) -> list[dict]:
    """
    Convert raw FDA JSON into a flat list of chunk documents.
    Each document has: text, drug, section, source, chunk_index
    """
    documents = []

    if not raw_data.get("results"):
        print(f"  WARNING: no results found for {drug_name}")
        return documents

    label = raw_data["results"][0]

    for section in RELEVANT_SECTIONS:
        if section not in label:
            continue  # this drug's label doesn't have this section — skip it

        section_content = label[section]
        # openFDA fields are lists of strings — join them into one block
        full_text = " ".join(section_content) if isinstance(section_content, list) else str(section_content)

        chunks = simple_chunk_text(full_text)
        for i, chunk_text in enumerate(chunks):
            documents.append({
                "text": chunk_text,
                "drug": drug_name,
                "section": section,
                "source": "FDA Drug Label",
                "chunk_index": i,
            })

    return documents


def process_all_to_documents() -> list[dict]:
    """Load all raw FDA files, normalize + chunk them, return one flat list."""
    all_documents = []
    for drug in DRUG_NAMES:
        print(f"Processing: {drug}")
        raw = load_raw(drug)
        docs = normalize_drug_label(drug, raw)
        print(f"  -> {len(docs)} chunks created")
        all_documents.extend(docs)
    return all_documents

if __name__ == "__main__":
    ingest_all()
    print("\n--- Normalizing and chunking ---")
    docs = process_all_to_documents()
    print(f"\nTotal chunks across all drugs: {len(docs)}")
    print("\nSample chunk:")
    print(docs[0])