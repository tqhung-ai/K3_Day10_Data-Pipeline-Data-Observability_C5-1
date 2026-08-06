# Role 4 — RAG & Agent handoff (Checkpoint 0)

## Scope

Role 4 owns the retrieval and agent contract. Checkpoint 0 freezes the input/output contract and prepares smoke checks; it does not run the final embedding build.

## Frozen contract

### Input

- Source: `data/clean/papers_clean.csv` or `data/clean/papers_clean.json`.
- Required fields for indexing:
  - `paper_id`
  - `title`
  - `text_for_embedding`
  - `published`
  - `authors_joined`
  - `categories_joined`
  - `summary`
  - `abs_url`
  - `pdf_url`
- Document identity is the stable `paper_id`; the Chroma row ID is `{paper_id}::{row_index}`.

### Embedding and collections

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
- Backend: persistent ChromaDB with cosine distance.
- Persist directory: `data/chroma/`.
- Baseline manifest: `data/embeddings/papers_embeddings.json`.
- Baseline collection: `papers-baseline`.
- Corrupted collection: `papers-corrupted`.
- Repaired collection: `papers-repaired`.

Corrupted and repaired collections must remain separate from baseline. All three states must use the same embedding model, test set and `top_k` when compared.

### Retrieval and agent behavior

- `LocalEmbeddingIndex.search(query, top_k)` returns paper ID, title, cosine-derived score, content and metadata.
- `LocalEmbeddingIndex.lookup(value)` supports exact case-insensitive `paper_id` or title lookup.
- The agent exposes `semantic_search_papers` and `lookup_paper` tools.
- Factual agent questions must use a tool first; unsupported answers must clearly say the corpus does not support them.

## Smoke checks prepared for CP2

1. Semantic query: `retrieval augmented generation large language model`.
2. Exact lookup by ID: `10.2118/234689-pa`.
3. Exact lookup by title: `SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation`.
4. Factual QA after indexing: ask who authored the SafeRAG paper and verify the answer against `authors_joined`.

Expected evidence after CP2:

- `papers_embeddings.json` exists and declares the model, persist path, collection name and indexed documents.
- Semantic search returns at least one result for the smoke query.
- ID and exact-title lookup return the same `paper_id`.
- Agent output is grounded in the returned tool content.

## CP0 status

- [x] Read and confirmed the `embeddings`, `index`, `qa` and `agent` interfaces.
- [x] Frozen model, collection names, metadata and artifact paths.
- [x] Prepared reproducible semantic-search, ID-lookup and title-lookup smoke checks.
- [x] Verified the current clean input contains the required indexing fields for 24 rows.
- [x] Embedding manifest and Chroma collections were completed in CP2 and retained
  separately for baseline, corrupted and repaired states.
