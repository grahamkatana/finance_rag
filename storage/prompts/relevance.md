You are an expert evaluator for RAG systems.

Your task is to evaluate whether the retrieved CONTEXT is relevant to the QUERY.
Relevant context contains information that would help answer the query.

QUERY:
{query}

RETRIEVED CONTEXT:
{context}

Score the relevance from 0.0 to 1.0 where:
1.0 = context is perfectly relevant and contains the answer
0.5 = context is partially relevant
0.0 = context is completely irrelevant to the query

Respond with ONLY a number between 0.0 and 1.0.
Score: