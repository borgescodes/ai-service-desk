from ai_service_desk.web.business_context import BusinessVocabulary


def test_ubs_is_recognized_as_context_but_not_as_cdm() -> None:
    vocabulary = BusinessVocabulary()

    assert vocabulary.systems("Preciso de acesso ao UBS") == ("UBS",)
    assert vocabulary.systems("Preciso de acesso ao UBS") != ("CDM",)
