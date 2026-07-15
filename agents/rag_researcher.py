"""
============================================================
 Genesis AI — RAG Researcher Agent (agents/rag_researcher.py)
 Handles PDF ingestion, embedding, and semantic retrieval
 using a local ChromaDB vector store.

 Supported operations:
   - ingest_pdf(filepath)  → chunks + embeds a document
   - query(text)           → returns top-k relevant passages
   - knowledge_search()    → full-text semantic search
   - detect_research_gaps()→ identifies under-covered topics
   - check_patent_novelty()→ checks claim uniqueness vs corpus
============================================================
"""

import os
import re
import logging
import hashlib
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

# Maximum characters per text chunk fed to the embedder
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100   # Characters of overlap between adjacent chunks


class RAGResearcher:
    """
    Manages a persistent ChromaDB collection for document-grounded Q&A.

    The collection uses ChromaDB's default Sentence-Transformers embedding
    function (all-MiniLM-L6-v2) which runs locally — no external API call.
    """

    COLLECTION_NAME = "genesis_knowledge_base"

    def __init__(self):
        chroma_path = os.environ.get("CHROMA_DB_PATH", "./chroma_store")

        # Persistent client saves the vector index to disk across restarts
        self._client = chromadb.PersistentClient(path=chroma_path)

        # Sentence-Transformers embedder — runs locally, zero cost
        self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Get-or-create ensures idempotent startup
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedder,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "RAGResearcher initialised — collection '%s' has %d documents.",
            self.COLLECTION_NAME,
            self._collection.count(),
        )

    # ------------------------------------------------------------------
    #  Ingestion
    # ------------------------------------------------------------------

    def ingest_pdf(self, filepath: str) -> dict:
        """
        Parse a PDF file, split into overlapping chunks, and embed into ChromaDB.

        The parser uses pdfkit-style raw text extraction.  For production
        deployments with complex PDFs, swap this for PyMuPDF (fitz).

        Args:
            filepath: Absolute or relative path to the PDF on disk.

        Returns:
            A summary dict: {filename, chunks_added, total_docs}.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF not found at: {filepath}")

        filename = os.path.basename(filepath)
        logger.info("Ingesting PDF: %s", filename)

        # --- Extract text (basic extraction via pdfkit binary subprocess) ---
        raw_text = self._extract_text_from_pdf(filepath)

        if not raw_text.strip():
            raise ValueError(f"No extractable text found in {filename}.")

        # --- Chunk the text with overlap ---
        chunks = self._chunk_text(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)
        logger.info("  → %d chunks created from %s", len(chunks), filename)

        # --- Build unique IDs so re-ingesting the same file is idempotent ---
        doc_hash = hashlib.md5(raw_text.encode()).hexdigest()[:8]
        ids       = [f"{doc_hash}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]

        # Upsert — adds new chunks; skips duplicates by ID
        self._collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)

        return {
            "filename":    filename,
            "chunks_added": len(chunks),
            "total_docs":  self._collection.count(),
        }

    # ------------------------------------------------------------------
    #  Retrieval
    # ------------------------------------------------------------------

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        """
        Semantic similarity search against the knowledge base.

        Args:
            query_text: Natural-language query string.
            n_results:  Number of top passages to return.

        Returns:
            List of dicts: {text, source, score, chunk_index}.
        """
        if self._collection.count() == 0:
            logger.warning("ChromaDB collection is empty — returning no results.")
            return []

        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        passages = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            passages.append({
                "text":        text,
                "source":      meta.get("source", "unknown"),
                "chunk_index": meta.get("chunk_index", 0),
                "score":       round(1 - dist, 4),   # cosine similarity
            })

        return passages

    def knowledge_search(self, query: str, n_results: int = 8) -> dict:
        """
        Full knowledge-base semantic search.  Returns results grouped by source.
        """
        passages = self.query(query, n_results=n_results)
        grouped  = {}
        for p in passages:
            grouped.setdefault(p["source"], []).append(p)

        return {
            "query":   query,
            "total":   len(passages),
            "results": grouped,
        }

    def detect_research_gaps(self, topic: str) -> dict:
        """
        Identify topics related to `topic` that are minimally covered in the corpus.
        Uses inverse document frequency heuristic: low-scoring passages indicate gaps.

        Returns a dict with 'well_covered' and 'gaps' lists.
        """
        passages = self.query(topic, n_results=10)

        well_covered = [p for p in passages if p["score"] >= 0.5]
        gap_passages = [p for p in passages if p["score"] < 0.5]

        return {
            "topic":        topic,
            "well_covered": [p["text"][:200] for p in well_covered],
            "gaps":         [p["text"][:200] for p in gap_passages],
            "gap_count":    len(gap_passages),
        }

    def check_patent_novelty(self, claim_text: str) -> dict:
        """
        Check whether a patent claim appears novel relative to the ingested corpus.
        A cosine similarity > 0.85 suggests prior art; < 0.4 suggests novelty.

        Returns a dict with novelty_score and recommendation.
        """
        passages = self.query(claim_text, n_results=3)

        if not passages:
            return {
                "claim":           claim_text[:200],
                "novelty_score":   1.0,
                "recommendation":  "No prior art found in corpus — appears novel.",
                "prior_art_found": False,
            }

        max_similarity  = max(p["score"] for p in passages)
        novelty_score   = round(1 - max_similarity, 4)
        prior_art_found = max_similarity > 0.85

        return {
            "claim":          claim_text[:200],
            "novelty_score":  novelty_score,
            "top_similarity": max_similarity,
            "recommendation": (
                "⚠ High similarity to existing document — potential prior art."
                if prior_art_found
                else "✓ Claim appears sufficiently novel relative to the corpus."
            ),
            "prior_art_found": prior_art_found,
            "closest_passages": [p["text"][:300] for p in passages[:2]],
        }

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _extract_text_from_pdf(self, filepath: str) -> str:
        """
        Extract raw text from a PDF.
        Attempts PyMuPDF first (fastest, best quality); falls back to
        a basic binary read that works for simple text-only PDFs.
        """
        try:
            import fitz  # PyMuPDF — optional high-quality extractor
            doc  = fitz.open(filepath)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            pass  # PyMuPDF not installed — use fallback

        # Fallback: read file as bytes and decode printable ASCII
        with open(filepath, "rb") as f:
            raw = f.read()
        # Strip PDF binary noise; keep printable characters
        text = re.sub(rb"[^\x20-\x7e\n\t]", b" ", raw).decode("ascii", errors="ignore")
        # Collapse long whitespace runs
        text = re.sub(r"\s{3,}", "\n", text)
        return text

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """
        Split `text` into overlapping fixed-size character chunks.
        Chunks honour sentence boundaries when possible.
        """
        chunks  = []
        start   = 0
        length  = len(text)

        while start < length:
            end = min(start + chunk_size, length)

            # Try to break at a sentence boundary ('. ', '? ', '! ')
            if end < length:
                boundary = max(
                    text.rfind(". ", start, end),
                    text.rfind("? ", start, end),
                    text.rfind("! ", start, end),
                )
                if boundary > start + overlap:
                    end = boundary + 2  # include the punctuation + space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start += chunk_size - overlap  # slide forward with overlap

        return chunks
