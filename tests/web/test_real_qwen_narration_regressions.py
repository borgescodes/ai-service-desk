from ai_service_desk.web.conversation import operational_message


def _clarification_result() -> dict:
    return {
        "status": "NEEDS_CLARIFICATION",
        "request_id": None,
        "question": "Qual sistema esta com o problema?",
        "reason": "MISSING_SYSTEM",
    }


def test_clarification_uses_backend_question_without_model_call() -> None:
    calls = []

    def chat(payload: dict) -> dict:
        calls.append(payload)
        raise AssertionError("Deterministic fallback must not call the model.")

    result = _clarification_result()
    rendered = operational_message(
        result,
        "Preciso de acesso ao sistema.",
        chat,
    )

    assert calls == []
    assert rendered == "Entendi.\n\nQual sistema esta com o problema?"
    assert rendered.endswith(result["question"])


def test_clarification_cannot_leak_model_meta_instruction() -> None:
    calls = []

    def chat(payload: dict) -> dict:
        calls.append(payload)
        return {
            "message": {
                "content": ('{"assistant_message": "Como solicitado, nao posso responder."}')
            }
        }

    rendered = operational_message(
        _clarification_result(),
        "Preciso pedir material para uma revenda.",
        chat,
    )

    assert calls == []
    assert "como solicitado" not in rendered.casefold()
    assert rendered == "Entendi.\n\nQual sistema esta com o problema?"


def test_office_clarification_preserves_backend_question_verbatim() -> None:
    calls = []

    def chat(payload: dict) -> dict:
        calls.append(payload)
        raise AssertionError("Deterministic fallback must not call the model.")

    result = _clarification_result()
    rendered = operational_message(
        result,
        "Esqueci minha senha do Office e nao consigo entrar.",
        chat,
    )

    assert calls == []
    assert rendered == f"Entendi.\n\n{result['question']}"


def test_clarification_cannot_append_model_generated_question() -> None:
    calls = []

    def chat(payload: dict) -> dict:
        calls.append(payload)
        return {
            "message": {"content": ('{"assistant_message": "Voce se refere ao Microsoft 365?"}')}
        }

    result = _clarification_result()
    rendered = operational_message(
        result,
        "Estou com problema de acesso.",
        chat,
    )

    assert calls == []
    assert "microsoft 365" not in rendered.casefold()
    assert rendered == f"Entendi.\n\n{result['question']}"
