# Individual Report — Role 4: RAG, Embedding & Agent

## Scope

| Thành viên | MSSV |
|---|---|
| Nguyễn Đức Sơn | 2A202601485 |

Role 4 owns the embedding/index contract, retrieval and grounded agent path.

## Work and evidence

- Uses `sentence-transformers/all-MiniLM-L6-v2` with persistent ChromaDB and
  cosine distance.
- Maintains separate collections `papers-baseline`, `papers-corrupted` and
  `papers-repaired`, each with 24 documents.
- `LocalEmbeddingIndex.search()` and `lookup()` provide semantic and exact-ID/title
  retrieval for the agent.
- Evidence: manifests in `data/embeddings/` and three collection counts.

## Technical understanding

Each indexed document keeps stable `paper_id`, title, metadata and
`text_for_embedding`. All states use the same model, `top_k=4` and evaluation
set. Retrieval hit rate is `1.0` in baseline, corrupted and repaired runs.

## Result

The corrupted content reduced token-F1 even though retrieval hit rate stayed
perfect; repaired embeddings restore the baseline answer overlap.
