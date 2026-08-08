"""
Surgical re-embed of ONLY the 3 corrected drugs (metformin, amoxicillin,
lisinopril) whose source files were fixed from combination-product labels to
clean single-ingredient labels.

What it does:
  1. Deletes existing chunks for ONLY these 3 drugs from ChromaDB.
  2. Re-chunks their corrected JSON and re-adds them.
The other 12 drugs are never touched. Embeddings are local (sentence-
transformers), so this makes NO Gemini/OpenAI calls and uses no quota.

Run:  python reembed_fixed.py
"""
from app.ingestion.fda_ingest import load_raw, normalize_drug_label
from app.retrieval.vector_store import get_or_create_collection, add_documents

DRUGS_TO_REEMBED = ["metformin", "amoxicillin", "lisinopril"]


def main():
    collection = get_or_create_collection()

    before = collection.count()
    print(f"ChromaDB chunk count before: {before}")

    # 1) Delete existing chunks for ONLY these 3 drugs.
    for drug in DRUGS_TO_REEMBED:
        collection.delete(where={"drug": drug})
        print(f"  deleted existing chunks for: {drug}")

    after_delete = collection.count()
    print(f"ChromaDB chunk count after delete: {after_delete}")

    # 2) Re-chunk the corrected JSON for each and re-add.
    new_docs = []
    for drug in DRUGS_TO_REEMBED:
        raw = load_raw(drug)                         # reads corrected data/raw_fda/<drug>.json
        docs = normalize_drug_label(drug, raw)       # same chunking as the full pipeline
        print(f"  {drug}: {len(docs)} fresh chunks")
        new_docs.extend(docs)

    added = add_documents(new_docs)
    after_add = collection.count()
    print(f"Re-added {added} chunks.")
    print(f"ChromaDB chunk count after re-add: {after_add}")
    print("\nDone. Only the 3 corrected drugs were replaced; the other 12 are untouched.")


if __name__ == "__main__":
    main()