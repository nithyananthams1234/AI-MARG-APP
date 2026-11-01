from app.prompts.templates import chat_prompt


def test_chat_prompt_requests_concise_grounded_bullet_answers():
    prompt = chat_prompt(
        "How can I teach equivalent fractions?",
        [{"text": "Use fraction strips.", "document": "fractions.pdf", "page": 4}],
        None,
    )

    assert "under 90 words" in prompt
    assert "exactly 3 brief bullet points" in prompt
    assert "at most 18 words" in prompt
    assert "Cite supported claims inline as [S<n>]" in prompt
    assert "use only retrieved passages for educational claims" in prompt
    assert "Treat clearly labeled historical records" in prompt
    assert "never present them as current facts" in prompt
    assert "[S1] fractions.pdf (page 4)" in prompt
