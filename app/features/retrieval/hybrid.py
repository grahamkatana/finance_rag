from dataclasses import dataclass, field


@dataclass
class SearchResult:
    qdrant_id: str
    score: float
    source: str
    metadata: dict = field(default_factory=dict)


def reciprocal_rank_fusion(
    qdrant_results: list[SearchResult],
    postgres_results: list[SearchResult],
    k: int = 60,
    top_n: int = 5,
) -> list[SearchResult]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    Formula for each document:
        RRF(d) = sum(1 / (k + rank(d, list)))

    Where:
        k   = smoothing constant (60 is standard)
        rank = position in the list (1-indexed)

    Documents appearing in both lists get scores from both,
    naturally boosting them above single-list results.
    """
    # 1. Accumulate RRF scores per qdrant_id
    rrf_scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    # 2. Score Qdrant results
    for rank, result in enumerate(qdrant_results, start=1):
        rrf_scores[result.qdrant_id] = (
            rrf_scores.get(result.qdrant_id, 0.0) + 1.0 / (k + rank)
        )
        result_map[result.qdrant_id] = result

    # 3. Score Postgres results
    for rank, result in enumerate(postgres_results, start=1):
        rrf_scores[result.qdrant_id] = (
            rrf_scores.get(result.qdrant_id, 0.0) + 1.0 / (k + rank)
        )
        # Only add to map if not already there
        if result.qdrant_id not in result_map:
            result_map[result.qdrant_id] = result

    # 4. Build final sorted results
    fused = []
    for qdrant_id, score in rrf_scores.items():
        original = result_map[qdrant_id]
        fused.append(SearchResult(
            qdrant_id=qdrant_id,
            score=score,
            source="hybrid",
            metadata=original.metadata,
        ))

    # 5. Sort by score descending and limit
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused[:top_n]