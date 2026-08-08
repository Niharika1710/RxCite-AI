"""
Re-fetch ONLY the 3 contaminated drugs (metformin, amoxicillin, lisinopril),
selecting the clean SINGLE-INGREDIENT label instead of openFDA's first result
(which was a combination product).

Safe: overwrites only these 3 files in data/raw_fda/. Does NOT touch the other
12 drug files, and does NOT touch ChromaDB. Re-embedding is a separate step you
run only after verifying these files look right.

Run:  python refetch_fix.py
"""
import json
import os
import time
import requests

FDA = "https://api.fda.gov/drug/label.json"
RAW_DATA_DIR = os.path.join("data", "raw_fda")

# The 3 drugs the audit flagged as combination-product contaminated.
DRUGS_TO_FIX = ["metformin", "amoxicillin", "lisinopril"]


def is_single_ingredient(label: dict, drug: str) -> bool:
    """True if this label is the single-ingredient form of `drug`."""
    names = label.get("openfda", {}).get("generic_name", [])
    if len(names) != 1:
        return False
    name = names[0].lower()
    # reject combinations like "sitagliptin and metformin hydrochloride"
    if " and " in name:
        return False
    # the requested drug must be the active ingredient named
    return drug.lower() in name


def fetch_clean_label(drug: str) -> dict | None:
    """Fetch candidates and return the FIRST clean single-ingredient label."""
    params = {"search": f'openfda.generic_name:"{drug}"', "limit": 10}
    r = requests.get(FDA, params=params, timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])

    for label in results:
        if is_single_ingredient(label, drug):
            # Return in the same shape fda_ingest expects: {"results": [label]}
            return {"results": [label]}
    return None


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    for drug in DRUGS_TO_FIX:
        print(f"Re-fetching clean label for: {drug}")
        try:
            clean = fetch_clean_label(drug)
            if clean is None:
                print(f"  !! No clean single-ingredient label found — SKIPPED (left as-is).")
                continue

            names = clean["results"][0].get("openfda", {}).get("generic_name", ["?"])
            ind = clean["results"][0].get("indications_and_usage", ["<none>"])[0][:90]
            path = os.path.join(RAW_DATA_DIR, f"{drug}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(clean, f, indent=2)
            print(f"  OK  generic_name={names}")
            print(f"      indication starts: {ind}")
            print(f"      saved -> {path}")
        except Exception as e:
            print(f"  ERROR: {e} — left existing file untouched.")
        time.sleep(1)

    print("\nDone. Re-fetched files written. ChromaDB NOT changed yet.")
    print("Next: verify with audit.py, then re-embed (separate step).")


if __name__ == "__main__":
    main()