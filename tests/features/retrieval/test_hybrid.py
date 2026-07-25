import pytest
from app.features.retrieval.hybrid import reciprocal_rank_fusion, SearchResult


@pytest.fixture
def qdrant_results():
    """Simulated Qdrant dense search results"""
    return [
        SearchResult(qdrant_id="a", score=0.95, source="qdrant"),
        SearchResult(qdrant_id="b", score=0.87, source="qdrant"),
        SearchResult(qdrant_id="c", score=0.76, source="qdrant"),
    ]


@pytest.fixture
def postgres_results():
    """Simulated Postgres BM25 sparse search results"""
    return [
        SearchResult(qdrant_id="b", score=0.91, source="postgres"),
        SearchResult(qdrant_id="d", score=0.85, source="postgres"),
        SearchResult(qdrant_id="a", score=0.72, source="postgres"),
    ]


def test_rrf_returns_list(qdrant_results, postgres_results):
    """RRF must return a list"""
    results = reciprocal_rank_fusion(qdrant_results, postgres_results)
    assert isinstance(results, list)


def test_rrf_returns_search_results(qdrant_results, postgres_results):
    """Every item must be a SearchResult"""
    results = reciprocal_rank_fusion(qdrant_results, postgres_results)
    assert all(isinstance(r, SearchResult) for r in results)


def test_rrf_merges_both_result_sets(qdrant_results, postgres_results):
    """All unique IDs from both searches must appear in output"""
    results = reciprocal_rank_fusion(qdrant_results, postgres_results)
    result_ids = {r.qdrant_id for r in results}
    assert "a" in result_ids
    assert "b" in result_ids
    assert "c" in result_ids
    assert "d" in result_ids


def test_rrf_scores_are_sorted_descending(qdrant_results, postgres_results):
    """Results must be sorted highest score first"""
    results = reciprocal_rank_fusion(qdrant_results, postgres_results)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rrf_boosts_results_appearing_in_both(qdrant_results, postgres_results):
    """
    IDs appearing in BOTH Qdrant and Postgres should
    rank higher than those appearing in only one.
    b and a appear in both — they should outrank c and d
    which appear in only one.
    """
    results = reciprocal_rank_fusion(qdrant_results, postgres_results)
    result_ids = [r.qdrant_id for r in results]

    # b appears in both at rank 2 (qdrant) and rank 1 (postgres)
    # d appears only in postgres
    assert result_ids.index("b") < result_ids.index("d")


def test_rrf_respects_k_parameter(qdrant_results, postgres_results):
    """
    k controls score smoothing — higher k = less reward
    for top ranks. Results should still be sorted correctly.
    """
    results_k10 = reciprocal_rank_fusion(
        qdrant_results, postgres_results, k=10
    )
    results_k60 = reciprocal_rank_fusion(
        qdrant_results, postgres_results, k=60
    )
    # Both should return same IDs, just different scores
    ids_k10 = {r.qdrant_id for r in results_k10}
    ids_k60 = {r.qdrant_id for r in results_k60}
    assert ids_k10 == ids_k60


def test_rrf_handles_empty_qdrant_results(postgres_results):
    """If Qdrant returns nothing, Postgres results should still work"""
    results = reciprocal_rank_fusion([], postgres_results)
    assert len(results) == len(postgres_results)


def test_rrf_handles_empty_postgres_results(qdrant_results):
    """If Postgres returns nothing, Qdrant results should still work"""
    results = reciprocal_rank_fusion(qdrant_results, [])
    assert len(results) == len(qdrant_results)


def test_rrf_handles_both_empty():
    """Both empty should return empty list gracefully"""
    results = reciprocal_rank_fusion([], [])
    assert results == []


def test_rrf_top_n_limits_results(qdrant_results, postgres_results):
    """top_n parameter should limit how many results come back"""
    results = reciprocal_rank_fusion(
        qdrant_results, postgres_results, top_n=2
    )
    assert len(results) == 2