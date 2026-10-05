from unittest.mock import AsyncMock, patch

from app.tasks.audit import process_query_audit


def _run(**extra):
    with patch("app.tasks.audit._run_eval", new_callable=AsyncMock, return_value=(0.9, 0.8)) as run_eval, \
         patch("app.tasks.audit._write_audit", new_callable=AsyncMock) as write:
        process_query_audit.run(
            query="And services?", answer="a", chunks=[{"chunk_text": "t"}], model_used="m",
            embed_model_used="e", duration_ms=1.0, client_id="1", **extra,
        )
    return run_eval.await_args.kwargs, write.await_args.kwargs


def test_relevance_is_judged_against_what_was_searched_for_but_the_audit_keeps_what_was_typed():
    scored, written = _run(search_query="What were Apple's services net sales in fiscal 2024?")
    assert scored["query"] == "What were Apple's services net sales in fiscal 2024?"
    assert written["query"] == "And services?"


def test_without_a_search_query_the_typed_question_is_scored_as_before():
    scored, written = _run()
    assert scored["query"] == written["query"] == "And services?"
