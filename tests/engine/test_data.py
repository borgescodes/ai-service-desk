from pathlib import Path

import pandas as pd
import pytest

from ai_service_desk.engine.data import clean_text, load_corpus, prepare_tiflux, sanitize, sensitive


def write_csv(path: Path, rows: list[dict], sep: str = ";") -> Path:
    pd.DataFrame(rows).to_csv(path, sep=sep, index=False, encoding="utf-8-sig")
    return path


def test_load_corpus_preserves_text_ids_and_marks_history(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "corpus.csv",
        [
            {
                "ticket_id": "0001",
                "ticket_number": "42",
                "title": "A",
                "texto_busca": "falha A",
                "historico_atendimento": "acao B",
            }
        ],
    )
    data = load_corpus(path)
    assert data.iloc[0].ticket_id == "0001"
    assert data.iloc[0].status_conhecimento == "HISTORICO_NAO_VALIDADO"


def test_load_corpus_rejects_duplicate_empty_and_missing_values(tmp_path: Path) -> None:
    row = {"ticket_id": "1", "ticket_number": "2", "title": "A", "texto_busca": "x"}
    with pytest.raises(ValueError):
        load_corpus(write_csv(tmp_path / "dupe.csv", [row, row]))
    with pytest.raises(ValueError):
        load_corpus(write_csv(tmp_path / "missing.csv", [{"x": "a"}]))
    with pytest.raises(ValueError):
        load_corpus(write_csv(tmp_path / "empty.csv", [row | {"texto_busca": " "}]))


def test_clean_text_removes_html_scripts_and_controls() -> None:
    assert (
        clean_text("<p>Falha &amp; teste</p><script>alert(1)</script>\x1b[31m") == "Falha & teste"
    )


def test_sanitize_masks_contacts_but_preserves_system_name() -> None:
    out = sanitize(
        "CIGAM a@empresa.com 192.168.1.7 https://intra/test 123.456.789-00 (91) 99999-8888"
    )
    assert "CIGAM" in out
    for marker in ("[EMAIL]", "[IP]", "[URL]", "[CPF]", "[TELEFONE]"):
        assert marker in out


def test_sensitive_filter_is_conservative() -> None:
    assert sensitive("senha: ABC123")
    assert sensitive("api_key: not-real")
    assert not sensitive("rotina 1024 do CIGAM")


def test_prepare_orders_notes_filters_status_scope_and_sensitive(tmp_path: Path) -> None:
    tickets = [
        {
            "id": "1",
            "ticket_number": "101",
            "title": "Falha CIGAM",
            "description": "<p>Nao abre</p>",
            "is_closed": "true",
            "status_name": "closed",
            "services_catalog_name": "Sistemas",
        },
        {
            "id": "2",
            "ticket_number": "102",
            "title": "Aberto",
            "description": "x",
            "is_closed": "false",
            "status_name": "open",
            "services_catalog_name": "Sistemas",
        },
        {
            "id": "3",
            "ticket_number": "103",
            "title": "Cancelado",
            "description": "x",
            "is_closed": "true",
            "status_name": "cancelado",
            "services_catalog_name": "Sistemas",
        },
        {
            "id": "4",
            "ticket_number": "104",
            "title": "Sensivel",
            "description": "senha: abc",
            "is_closed": "true",
            "status_name": "closed",
            "services_catalog_name": "Sistemas",
        },
        {
            "id": "5",
            "ticket_number": "105",
            "title": "RH",
            "description": "duvida",
            "is_closed": "true",
            "status_name": "closed",
            "services_catalog_name": "Recursos Humanos",
        },
    ]
    notes = [
        {
            "id": "11",
            "ticket_id": "1",
            "created_at": "2026-08-02",
            "description": "Segundo apontamento",
        },
        {
            "id": "10",
            "ticket_id": "1",
            "created_at": "2026-08-01",
            "description": "Primeiro apontamento",
        },
        {"id": "12", "ticket_id": "999", "created_at": "2026-08-01", "description": "Orfao"},
    ]
    t = write_csv(tmp_path / "tickets.csv", tickets, "\t")
    a = write_csv(tmp_path / "notes.csv", notes, "\t")
    data, report = prepare_tiflux(t, a, scope="ti")
    assert data.ticket_id.tolist() == ["1"]
    assert data.iloc[0].historico_atendimento == "Primeiro apontamento\nSegundo apontamento"
    assert report["apontamentos_orfaos"] == 1
    assert report["excluidos_abertos_ou_cancelados"] == 2
    assert report["excluidos_fora_escopo"] == 1
    assert report["excluidos_sensiveis"] == 1


def test_prepare_removes_generic_notes_and_limits_search_text(tmp_path: Path) -> None:
    tickets = [
        {
            "id": "1",
            "ticket_number": "1",
            "title": "A",
            "description": "x" * 7000,
            "is_closed": "true",
            "status_name": "closed",
        }
    ]
    notes = [{"id": "1", "ticket_id": "1", "description": "resolvido", "created_at": "2026-01-01"}]
    data, report = prepare_tiflux(
        write_csv(tmp_path / "t.csv", tickets, "\t"),
        write_csv(tmp_path / "a.csv", notes, "\t"),
        scope="todos",
    )
    assert len(data.iloc[0].texto_busca) == 6000
    assert data.iloc[0].historico_atendimento == ""
    assert report["textos_limitados"] == 1
    assert report["mensagens_genericas_removidas"] == 1
