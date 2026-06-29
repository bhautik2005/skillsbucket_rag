"""
SKILLSBUCKET RAG — PHASE 2 + 3: LLM CHAIN + FASTAPI BACKEND
=============================================================
Starts the production API server.

Command:
    uvicorn app_api:app --reload --port 8000

Supports two LLM backends (set LLM_PROVIDER in .env):
    LLM_PROVIDER=mistral   → uses ChatMistralAI (mistral-small-2506)
    LLM_PROVIDER=gemini    → uses Google Gemini 2.5 Flash

Endpoints:
    POST /chat          → general Q&A about Skillsbucket
    POST /proposal      → generate a full corporate training proposal
    GET  /health        → system health check
    GET  /stats         → knowledge base statistics
"""

import os
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# LangChain LCEL
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ChromaDB
import chromadb
from chromadb.utils import embedding_functions

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
CHROMA_PATH   = "./chroma_db"
COLLECTION    = "skillsbucket_proposals"
EMBED_MODEL   = "all-MiniLM-L6-v2"
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "mistral").lower()   # "mistral" or "gemini"
N_RESULTS     = 6    # number of chunks to retrieve per query

# Load prompt templates from files
PROMPTS_DIR = Path("./prompts")

def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt file {filename} not found — using inline fallback.")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# LLM INITIALISATION — Choose your provider
# ══════════════════════════════════════════════════════════════════════════════

def initialise_llm():
    """
    Initialises the LLM based on LLM_PROVIDER env variable.
    Both are set to temperature=0.1 for tight, factual responses.

    For Mistral: set MISTRAL_API_KEY in .env
    For Gemini:  set GOOGLE_API_KEY in .env
    """
    if LLM_PROVIDER == "gemini":
        # ── Google Gemini 2.5 Flash ──────────────────────────────────────────
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise EnvironmentError("GOOGLE_API_KEY not set in .env")
            log.info("LLM: Google Gemini 2.5 Flash")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.1,
                google_api_key=api_key,
            )
        except ImportError:
            raise ImportError("Install: pip install langchain-google-genai")

    else:
        # ── Mistral AI (default) ─────────────────────────────────────────────
        try:
            from langchain_mistralai import ChatMistralAI
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise EnvironmentError("MISTRAL_API_KEY not set in .env")
            log.info("LLM: Mistral mistral-small-2506")
            return ChatMistralAI(
                model="mistral-small-2506",
                temperature=0.1,
                api_key=api_key,
            )
        except ImportError:
            raise ImportError("Install: pip install langchain-mistralai")


# ══════════════════════════════════════════════════════════════════════════════
# LCEL CHAIN BUILDERS
# Two separate chains:
#   1. chat_chain    — general Q&A, tightly bounded to context
#   2. proposal_chain — full proposal generation using structured prompt
# ══════════════════════════════════════════════════════════════════════════════

GUARDRAIL_SYSTEM = """You are a helpful corporate assistant for Skillsbucket, a training and consulting company.

RULES:
1. You have access to the Skillsbucket knowledge base provided in {context} below.
2. Answer questions about Skillsbucket's courses, programs, services, pricing, and company information.
3. When the user asks for a "list", "all programs", "all courses", or similar — list EVERYTHING found in the context. Do not summarize or skip items.
4. When the user asks about pricing — extract and display ALL pricing details found in the context including per-day rates, mode multipliers, and payment terms.
5. When the user asks about the company, experience, or about Skillsbucket — answer from the about_us context.
6. Only refuse if the question is completely unrelated to Skillsbucket (e.g. cricket scores, cooking recipes, coding help).
7. NEVER invent information not in the context.
8. Answer in a professional, helpful tone. Use bullet points and tables where helpful."""

PROPOSAL_SYSTEM = load_prompt("proposal_system_prompt.txt") or """
You are a Corporate Proposal Generation Assistant for Skillsbucket.
Use ONLY the retrieved context to generate a professional proposal in Markdown.
Never invent information. If data is missing, state it is unavailable.
"""


def build_chat_chain(llm):
    """
    LCEL chain for general Q&A.
    pattern: prompt | llm | output_parser
    """
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(GUARDRAIL_SYSTEM),
        HumanMessagePromptTemplate.from_template("{question}")
    ])
    parser = StrOutputParser()
    return prompt | llm | parser


def build_proposal_chain(llm):
    """
    LCEL chain for full proposal generation.
    Takes all client context variables + retrieved context.
    """
    prompt = ChatPromptTemplate.from_template(PROPOSAL_SYSTEM)
    parser = StrOutputParser()
    return prompt | llm | parser


# ══════════════════════════════════════════════════════════════════════════════
# CHROMADB RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════

def initialise_collection():
    """Load the ChromaDB collection built by ingest.py."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    try:
        col = client.get_collection(name=COLLECTION, embedding_function=embed_fn)
        log.info(f"ChromaDB loaded — {col.count()} chunks in '{COLLECTION}'")
        return col
    except Exception as e:
        log.error(f"ChromaDB collection '{COLLECTION}' not found. Run ingest.py first.")
        raise e


def retrieve_context(
    collection,
    query: str,
    n_results: int = N_RESULTS,
    topic_filter: Optional[str] = None,
) -> tuple[str, int, list[str]]:
    """
    Semantic search over ChromaDB.
    Returns: (formatted_context_string, source_count, list_of_categories)
    """
    where = {"topic_label": {"$eq": topic_filter}} if topic_filter else None

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # Fallback to unfiltered if filtered returns nothing
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    docs      = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    if not docs:
        return "", 0, []

    # Format context for the LLM
    context_parts = []
    categories = set()
    for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances), 1):
        cat = meta.get("topic_label", "General")
        categories.add(cat)
        context_parts.append(
            f"[Source {i} | {cat} | {meta.get('file_name','')}]\n{doc}"
        )

    context_str = "\n\n---\n\n".join(context_parts)
    return context_str, len(docs), list(categories)


def retrieve_for_proposal(collection, client_context: dict) -> tuple[str, int, list[str]]:
    """
    Multi-query retrieval for proposal generation.
    Fetches context for each key area separately then merges.
    """
    queries = [
        client_context.get("training_course", "leadership training"),
        "pricing per day INR currency training_courses pricing_per_day mode_multiplier",
        "short_courses fixed_price online offline hybrid",
        "about skillsbucket company profile experience clients industries served",
        "terms and conditions cancellation payment",
        "contact information address email phone",
        "training methodology deliverables learning outcomes",
        "services executive coaching competency mapping",
    ]

    all_docs   = []
    all_cats   = set()

    for q in queries:
        results = collection.query(
            query_texts=[q],
            n_results=3,
            include=["documents", "metadatas"],
        )
        docs      = results["documents"][0]
        metadatas = results["metadatas"][0]
        for doc, meta in zip(docs, metadatas):
            if doc not in [d["text"] for d in all_docs]:   # deduplicate
                all_docs.append({"text": doc, "meta": meta})
                all_cats.add(meta.get("topic_label", "General"))

    context_parts = []
    for i, item in enumerate(all_docs, 1):
        cat = item["meta"].get("topic_label", "General")
        fn  = item["meta"].get("file_name", "")
        context_parts.append(f"[Source {i} | {cat} | {fn}]\n{item['text']}")

    context_str = "\n\n---\n\n".join(context_parts)
    return context_str, len(all_docs), list(all_cats)


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP SETUP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Skillsbucket RAG API",
    description="Closed-book corporate training proposal assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise on startup
log.info("Starting Skillsbucket RAG API...")
llm        = initialise_llm()
chat_chain = build_chat_chain(llm)
prop_chain = build_proposal_chain(llm)
collection = initialise_collection()
log.info("API ready.")


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ClientContext(BaseModel):
    client_name:         str = "Client"
    company_name:        str = "Client Organization"
    industry:            str = "Corporate"
    training_course:     str = ""
    delivery_mode:       str = "ILT"
    participants:        str = "20"
    duration:            str = "2 Days"
    training_dates:      str = "To be confirmed"
    special_requirements:str = "None"

class ChatRequest(BaseModel):
    message:        str
    client_context: ClientContext = ClientContext()

class ProposalRequest(BaseModel):
    client_context: ClientContext

class ChatResponse(BaseModel):
    reply:          str
    sources_matched: int
    categories:     list[str]

class ProposalResponse(BaseModel):
    proposal_markdown: str
    sources_matched:   int
    categories:        list[str]


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status":        "ok",
        "llm_provider":  LLM_PROVIDER,
        "chunks_in_db":  collection.count(),
        "collection":    COLLECTION,
    }


@app.get("/stats")
def stats():
    """Returns distribution of topics in the knowledge base."""
    results = collection.get(include=["metadatas"], limit=5000)
    topic_dist = {}
    for meta in results["metadatas"]:
        t = meta.get("topic_label", "Unknown")
        topic_dist[t] = topic_dist.get(t, 0) + 1
    return {
        "total_chunks": collection.count(),
        "by_topic": topic_dist,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    General Q&A endpoint.
    Retrieves relevant context from ChromaDB and answers
    ONLY from that context. Refuses off-topic questions.
    """
    log.info(f"/chat — message: '{req.message[:60]}...'")

    # Build search query combining user message + context
    # Always fetch pricing and about_us alongside the main query
    main_query = f"{req.message} {req.client_context.training_course} {req.client_context.industry}".strip()

    # Retrieve main query results
    results_main = collection.query(
        query_texts=[main_query],
        n_results=6,
        include=["documents", "metadatas", "distances"],
    )

    # Always also retrieve pricing
    results_pricing = collection.query(
        query_texts=["pricing policy per day cost INR currency"],
        n_results=4,
        include=["documents", "metadatas"],
    )

    # Always also retrieve about us / company experience
    results_about = collection.query(
        query_texts=["about skillsbucket company experience clients industries"],
        n_results=3,
        include=["documents", "metadatas"],
    )

    # Merge all results, deduplicate
    seen = set()
    merged_docs = []
    categories = set()

    for docs, metas in [
        (results_main["documents"][0],    results_main["metadatas"][0]),
        (results_pricing["documents"][0], results_pricing["metadatas"][0]),
        (results_about["documents"][0],   results_about["metadatas"][0]),
    ]:
        for doc, meta in zip(docs, metas):
            if doc not in seen:
                seen.add(doc)
                merged_docs.append((doc, meta))
                categories.add(meta.get("topic_label", "General"))

    context = "\n\n---\n\n".join(
        f"[{meta.get('topic_label','')} | {meta.get('file_name','')}]\n{doc}"
        for doc, meta in merged_docs
    )
    sources = len(merged_docs)
    categories = list(categories)

    if not context:
        return ChatResponse(
            reply="I am sorry, but I do not have that specific company information inside my verified knowledge base.",
            sources_matched=0,
            categories=[],
        )

    try:
        reply = await chat_chain.ainvoke({
            "context":  context,
            "question": req.message,
        })
    except Exception as e:
        log.error(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    log.info(f"  → {sources} sources used, categories: {categories}")
    return ChatResponse(reply=reply, sources_matched=sources, categories=categories)


@app.post("/proposal", response_model=ProposalResponse)
async def generate_proposal(req: ProposalRequest):
    """
    Full proposal generation endpoint.
    Retrieves all relevant sections (course, pricing, about, T&C, contact)
    and generates a complete professional proposal in Markdown.
    """
    ctx = req.client_context
    log.info(f"/proposal — course: '{ctx.training_course}', client: '{ctx.company_name}'")

    context, sources, categories = retrieve_for_proposal(collection, ctx.dict())

    if not context:
        raise HTTPException(
            status_code=404,
            detail="No relevant content found in knowledge base for this request."
        )

    try:
        proposal_md = await prop_chain.ainvoke({
            "context":             context,
            "client_name":         ctx.client_name,
            "company_name":        ctx.company_name,
            "industry":            ctx.industry,
            "training_course":     ctx.training_course,
            "delivery_mode":       ctx.delivery_mode,
            "participants":        ctx.participants,
            "duration":            ctx.duration,
            "training_dates":      ctx.training_dates,
            "special_requirements":ctx.special_requirements,
        })
    except Exception as e:
        log.error(f"Proposal generation error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    log.info(f"  → Proposal generated — {sources} sources, {len(proposal_md)} chars")
    return ProposalResponse(
        proposal_markdown=proposal_md,
        sources_matched=sources,
        categories=categories,
    )