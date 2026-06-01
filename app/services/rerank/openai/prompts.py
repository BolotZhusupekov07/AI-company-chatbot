"""OpenAI rerank agent prompts."""

OPENAI_RERANK_INSTRUCTIONS = """
You rerank search results for a company knowledge assistant.
Return relevance scores from 0 to 1 for the input documents.
Include each input index at most once.
Only return documents that are relevant to the query, ordered from most relevant to least relevant.
""".strip()

OPENAI_RERANK_USER_PROMPT = "Rerank the documents from the provided context."
