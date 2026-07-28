You are an expert evaluator for RAG systems.

Your task is to evaluate whether the given ANSWER is faithful to the CONTEXT.
A faithful answer only contains information that is present in the context.
An unfaithful answer contains information not found in the context (hallucination).

CONTEXT:
{context}

ANSWER:
{answer}

Score the faithfulness from 0.0 to 1.0 where:
1.0 = answer is completely grounded in the context
0.5 = answer is partially grounded, some information not in context
0.0 = answer is completely hallucinated or not grounded in context

Respond with ONLY a number between 0.0 and 1.0.
Score: