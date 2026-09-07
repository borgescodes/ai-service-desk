import importlib

import pandas as pd
import pytest


def _module():
    return importlib.import_module("ai_service_desk.engine.demo_subset")


def _frame() -> pd.DataFrame:
    rows = [
        {"ticket_id": "c1", "title": "Falha CIGAM", "texto_busca": "Erro no CIGAM"},
        {"ticket_id": "c2", "title": "Rotina CIGAM", "texto_busca": "CIGAM rotina"},
        {"ticket_id": "s1", "title": "Falha SIAGRI", "texto_busca": "Erro no SIAGRI"},
        {"ticket_id": "s2", "title": "Rotina SIAGRI", "texto_busca": "SIAGRI rotina"},
        {"ticket_id": "p1", "title": "Impressora", "texto_busca": "Impressora nao imprime"},
        {"ticket_id": "p2", "title": "Impressao", "texto_busca": "Falha de impressao"},
        {"ticket_id": "a1", "title": "Acesso", "texto_busca": "Problema de acesso ao portal"},
        {"ticket_id": "a2", "title": "Login", "texto_busca": "Login nao entra"},
        {"ticket_id": "w1", "title": "Software", "texto_busca": "Instalar software interno"},
        {"ticket_id": "w2", "title": "Aplicativo", "texto_busca": "Instalacao de aplicativo"},
        {"ticket_id": "g1", "title": "Rede", "texto_busca": "Conexao de rede instavel"},
        {"ticket_id": "g2", "title": "Orientacao", "texto_busca": "Duvida operacional"},
    ]
    data = pd.DataFrame(rows)
    for column in ("ticket_number", "catalogo", "area", "item", "description", "mesa"):
        data[column] = ""
    data["status_conhecimento"] = "HISTORICO_NAO_VALIDADO"
    return data


def test_build_demo_subset_selects_six_unique_groups() -> None:
    module = _module()
    subset, report = module.build_demo_subset(_frame(), per_group=1)

    assert len(subset) == 6
    assert subset["ticket_id"].is_unique
    assert report["recipe"] == module.DEMO_RECIPE
    assert report["selected_rows"] == 6
    assert report["groups"] == {
        "cigam": 1,
        "siagri": 1,
        "printing": 1,
        "access": 1,
        "software": 1,
        "general": 1,
    }
    assert "ticket_id" not in report
    assert "title" not in report
    assert "texto_busca" not in report


def test_build_demo_subset_is_reproducible_across_input_order() -> None:
    module = _module()
    data = _frame()
    first, first_report = module.build_demo_subset(data, per_group=1)
    second, second_report = module.build_demo_subset(
        data.sample(frac=1, random_state=42).reset_index(drop=True),
        per_group=1,
    )

    assert first["ticket_id"].tolist() == second["ticket_id"].tolist()
    assert first_report == second_report


def test_build_demo_subset_rejects_insufficient_specific_group() -> None:
    module = _module()
    data = _frame()
    data = data[~data["texto_busca"].str.contains("SIAGRI")].copy()

    with pytest.raises(ValueError, match="siagri"):
        module.build_demo_subset(data, per_group=1)
