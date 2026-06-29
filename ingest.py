"""
SKILLSBUCKET RAG — PHASE 1: DATA INGESTION ENGINE
===================================================
Run this ONCE to build your local ChromaDB knowledge base.

Command:
    python ingest.py

What it does:
    1. Walks the entire output/ folder structure recursively
    2. Parses every JSON file and extracts all meaningful text fields
    3. Wraps each text fragment into a LangChain Document with rich metadata
    4. Embeds all documents using local HuggingFace model (no API key needed)
    5. Stores everything in ChromaDB at ./chroma_db
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

# LangChain
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

# ChromaDB
import chromadb
from chromadb.utils import embedding_functions

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
OUTPUT_DIR     = Path("./output")           # your JSON data folder
CHROMA_PATH    = "./chroma_db"              # where ChromaDB saves to disk
COLLECTION     = "skillsbucket_proposals"  # collection name inside ChromaDB
EMBED_MODEL    = "all-MiniLM-L6-v2"        # free local embedding model (~80MB)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — JSON PARSER
# Intelligently extracts tm any Skillext frosbucket JSON structure.
# Handles nested lists, dicts, and flat key-value pairs.
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_from_json(data: dict, prefix: str = "") -> list[str]:
    """
    Recursively walks a JSON dictionary and extracts all text values
    into clean, readable text fragments. Each fragment is semantically
    meaningful on its own — not just a raw key=value dump.
    """
    fragments = []

    # Priority fields — these are always extracted cleanly at the top level
    priority_keys = [
        "page_title", "program_name", "service_name", "company_name",
        "description", "program_overview", "mission", "vision",
        "tagline", "experience", "clients_served"
    ]

    for key, value in data.items():
        label = f"{prefix}{key}".replace("_", " ").title()

        if isinstance(value, str) and value.strip():
            # Simple string — add as "Label: Value"
            fragments.append(f"{label}: {value.strip()}")

        elif isinstance(value, list):
            # List of strings (e.g. learning_outcomes, key_topics)
            if all(isinstance(item, str) for item in value):
                items_text = "\n".join(f"  - {item}" for item in value)
                fragments.append(f"{label}:\n{items_text}")
            else:
                # List of dicts (e.g. pricing_tiers, terms clauses)
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        sub_fragments = extract_text_from_json(
                            item, prefix=f"{label} {i+1} — "
                        )
                        fragments.extend(sub_fragments)

        elif isinstance(value, dict):
            # Nested dict (e.g. agenda, headquarters, payment_terms)
            sub_fragments = extract_text_from_json(value, prefix=f"{label} → ")
            fragments.extend(sub_fragments)

    return fragments


def build_document(
    text_fragment: str,
    source_file: str,
    source_folder: str,
    topic_label: str,
    file_name: str,
    category: Optional[str] = None,
    program_name: Optional[str] = None,
) -> Document:
    """
    Wraps a text fragment into a LangChain Document with full metadata.
    This metadata is used for filtering at retrieval time.
    """
    return Document(
        page_content=text_fragment,
        metadata={
            "source_file":    source_file,     # full relative path
            "source_folder":  source_folder,   # top-level folder name
            "file_name":      file_name,        # just the filename
            "topic_label":    topic_label,      # human-readable category
            "category":       category or topic_label,
            "program_name":   program_name or "",
        }
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — FOLDER WALKER
# Recursively processes every JSON file in the output/ directory.
# Maps folder names to human-readable topic labels for metadata.
# ══════════════════════════════════════════════════════════════════════════════

# Maps folder path segments to readable topic labels
FOLDER_LABEL_MAP = {
    "about_skillsbucket":    "Company Profile",
    "commercial":            "Pricing and Commercial",
    "company":               "Contact Information",
    "terms_and_conditions":  "Terms and Conditions",
    "Services":              "Services",
    "leadership":            "Leadership Training",
    "business-communication":"Business Communication Training",
    "personal-effectiveness":"Personal Effectiveness Training",
    "sales":                 "Sales Training",
    "signature-program":     "Signature Programs",
    "team-building":         "Team Building Programs",
    "short_term_courses":    "Short Term Courses",
}


def resolve_topic_label(file_path: Path) -> str:
    """Determine human-readable topic label from file path parts."""
    parts = file_path.parts
    for part in reversed(parts[:-1]):   # walk backwards, skip the filename itself
        if part in FOLDER_LABEL_MAP:
            return FOLDER_LABEL_MAP[part]
    return "General"


def load_all_documents(output_dir: Path) -> list[Document]:
    """
    Walks the entire output/ directory, parses every JSON file,
    and returns a flat list of LangChain Documents.
    """
    all_docs: list[Document] = []
    json_files = list(output_dir.rglob("*.json"))

    log.info(f"Found {len(json_files)} JSON files to process.")

    for json_path in json_files:
        log.info(f"Processing: {json_path}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning(f"  Skipping {json_path} — JSON parse error: {e}")
            continue

        # Handle top-level list (e.g. Short Term Courses.json is a list of dicts)
        topic_label   = resolve_topic_label(json_path)
        source_folder = json_path.parts[1] if len(json_path.parts) > 1 else "root"
        if isinstance(data, list):
            log.info(f"  {json_path.name} is a list — processing each item separately")
            for item in data:
                if not isinstance(item, dict):
                    continue
                fragments = extract_text_from_json(item)
                program_name  = item.get("program_name") or item.get("service_name") or item.get("page_title", "")
                category      = item.get("category", topic_label)
                for fragment in fragments:
                    if len(fragment.strip()) < 20:
                        continue
                    doc = build_document(
                        text_fragment=fragment,
                        source_file=str(json_path),
                        source_folder=source_folder,
                        topic_label=topic_label,
                        file_name=json_path.name,
                        category=category,
                        program_name=program_name,
                    )
                    all_docs.append(doc)
            continue   # skip the normal dict processing below

        # Extract metadata fields directly from the JSON where available
        topic_label   = resolve_topic_label(json_path)
        program_name  = data.get("program_name") or data.get("service_name") or data.get("page_title", "")
        category      = data.get("category", topic_label)
        source_folder = json_path.parts[1] if len(json_path.parts) > 1 else "root"

        # Extract all text fragments from the JSON
        fragments = extract_text_from_json(data)

        if not fragments:
            log.warning(f"  No text extracted from {json_path.name}")
            continue

        # Build one Document per meaningful fragment
        for fragment in fragments:
            if len(fragment.strip()) < 20:   # skip trivially short fragments
                continue
            doc = build_document(
                text_fragment=fragment,
                source_file=str(json_path),
                source_folder=source_folder,
                topic_label=topic_label,
                file_name=json_path.name,
                category=category,
                program_name=program_name,
            )
            all_docs.append(doc)

        log.info(f"  → {len(fragments)} fragments extracted from {json_path.name}")

    log.info(f"Total documents built: {len(all_docs)}")
    return all_docs


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — CHROMADB STORAGE
# Initialises ChromaDB, creates the collection, embeds and inserts all docs.
# ══════════════════════════════════════════════════════════════════════════════

def ingest_to_chromadb(documents: list[Document]) -> None:
    """
    Takes the list of LangChain Documents, embeds them using
    the local HuggingFace model, and stores in ChromaDB.
    """
    log.info(f"Initialising ChromaDB at: {CHROMA_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Delete existing collection for a clean rebuild
    existing = [c.name for c in client.list_collections()]
    if COLLECTION in existing:
        log.info(f"Deleting existing collection '{COLLECTION}' for clean rebuild...")
        client.delete_collection(COLLECTION)

    # Use ChromaDB's built-in sentence-transformer embedding function
    # This keeps embeddings inside ChromaDB — no separate embedding step needed
    log.info(f"Loading embedding model: {EMBED_MODEL}")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}   # cosine similarity for text
    )
    log.info(f"Collection '{COLLECTION}' created.")

    # Prepare batch insertion
    ids        = [f"doc_{i:05d}" for i in range(len(documents))]
    texts      = [doc.page_content for doc in documents]
    metadatas  = [doc.metadata for doc in documents]

    # Insert in batches of 100 to avoid memory issues
    BATCH = 100
    total = len(documents)
    for start in range(0, total, BATCH):
        end = min(start + BATCH, total)
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
        log.info(f"  Inserted batch {start}–{end} of {total}")

    log.info("=" * 55)
    log.info("INGESTION COMPLETE")
    log.info(f"  Total chunks stored : {collection.count()}")
    log.info(f"  ChromaDB location   : {CHROMA_PATH}")
    log.info(f"  Collection name     : {COLLECTION}")
    log.info("=" * 55)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("SKILLSBUCKET RAG — Ingestion Pipeline Starting")
    log.info("=" * 55)

    if not OUTPUT_DIR.exists():
        log.error(f"Output directory '{OUTPUT_DIR}' not found.")
        log.error("Please ensure your JSON data files are in ./output/")
        raise SystemExit(1)

    # Phase 1: Load and parse all JSON documents
    documents = load_all_documents(OUTPUT_DIR)

    if not documents:
        log.error("No documents were extracted. Check your output/ folder.")
        raise SystemExit(1)

    # Phase 2: Embed and store in ChromaDB
    ingest_to_chromadb(documents)

    log.info("Ready. You can now start the API: uvicorn app_api:app --reload")