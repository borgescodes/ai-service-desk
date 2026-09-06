"""Local data preparation for unvalidated historical evidence."""

import html
import re
from pathlib import Path

import pandas as pd

from ai_service_desk.engine.validation import normalize_text

REQUIRED_COLUMNS = {"ticket_id", "ticket_number", "title", "texto_busca"}
TI_TERMS = (
    "sistemas",
    "helpdesk",
    "impressoras",
    "siagri",
    "redes e internet",
    "computadores",
    "banco de dados",
    "microsoft office",
    "suporte software",
    "cigam",
)
SENSITIVE = re.compile(r"\b(senha|password|passwd|credencia\w*|token|secret|api[ _-]?key)\b", re.I)
GENERIC = {"feito", "realizado", "resolvido", "ok", "em atendimento", "finalizado", "concluido"}


def clean_text(value: str) -> str:
    text = html.unescape(str(value))
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return " ".join(text.split())


def sensitive(text: str) -> bool:
    return bool(SENSITIVE.search(normalize_text(text)))


def sanitize(text: str, name_pattern: re.Pattern | None = None) -> str:
    value = clean_text(text)
    value = re.sub(r"https?://\S+|www\.\S+", "[URL]", value, flags=re.I)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
    value = re.sub(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", "[IP]", value)
    value = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[CPF]", value)
    value = re.sub(
        r"(?<!\w)(?:\+55\s*)?\(?\d{2}\)?\s*9?\d{4}[- ]\d{4}(?!\d)",
        "[TELEFONE]",
        value,
    )
    if name_pattern:
        value = name_pattern.sub("[PESSOA]", value)
    return value


def load_corpus(path: str | Path) -> pd.DataFrame:
    data = pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError("Colunas ausentes: " + ", ".join(sorted(missing)))
    if data.empty:
        raise ValueError("Corpus vazio.")
    if data.ticket_id.str.strip().eq("").any() or data.ticket_id.duplicated().any():
        raise ValueError("ticket_id vazio ou duplicado. Corrija antes de indexar.")
    if data.texto_busca.str.strip().eq("").any():
        raise ValueError("texto_busca vazio em algum registro.")
    for column in ("catalogo", "area", "item", "historico_atendimento", "description", "mesa"):
        if column not in data:
            data[column] = ""
    data["status_conhecimento"] = "HISTORICO_NAO_VALIDADO"
    return data.reset_index(drop=True)


def _name_pattern(tickets: pd.DataFrame, appointments: pd.DataFrame) -> re.Pattern | None:
    names: set[str] = set()
    for data, columns in [
        (tickets, ("requestor_name", "responsible_name")),
        (appointments, ("appointment_user_name", "requestor_name")),
    ]:
        for column in columns:
            if column in data:
                names.update(
                    clean_text(value)
                    for value in data[column]
                    if len(clean_text(value)) >= 8 and len(clean_text(value).split()) >= 2
                )
    if not names:
        return None
    expression = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{expression})(?!\w)", re.I)


def prepare_tiflux(
    tickets: str | Path,
    appointments: str | Path,
    scope: str = "ti",
) -> tuple[pd.DataFrame, dict]:
    if scope not in ("ti", "todos"):
        raise ValueError("Escopo deve ser ti ou todos.")
    ticket_data = pd.read_csv(
        tickets, sep="\t", encoding="utf-8-sig", dtype=str, keep_default_na=False
    )
    appointment_data = pd.read_csv(
        appointments, sep="\t", encoding="utf-8-sig", dtype=str, keep_default_na=False
    )
    ticket_required = {"id", "ticket_number", "title", "description", "is_closed", "status_name"}
    appointment_required = {"id", "ticket_id", "description"}
    if not ticket_required <= set(ticket_data.columns):
        raise ValueError("CSV de tickets nao tem as colunas Tiflux esperadas (separador: tabulacao).")
    if not appointment_required <= set(appointment_data.columns):
        raise ValueError("CSV de apontamentos nao tem as colunas esperadas.")
    for data in (ticket_data, appointment_data):
        if data.id.duplicated().any() or data.id.str.strip().eq("").any():
            raise ValueError("IDs vazios ou duplicados no CSV de origem.")

    report = {
        "tickets_lidos": len(ticket_data),
        "apontamentos_lidos": len(appointment_data),
        "escopo": scope,
        "apontamentos_orfaos": int((~appointment_data.ticket_id.isin(ticket_data.id)).sum()),
        "excluidos_sensiveis": 0,
        "textos_limitados": 0,
        "mensagens_genericas_removidas": 0,
    }
    names = _name_pattern(ticket_data, appointment_data)
    closed = ticket_data.is_closed.str.lower().eq("true") & ~ticket_data.status_name.str.lower().str.contains(
        "cancel", regex=False
    )
    report["excluidos_abertos_ou_cancelados"] = int((~closed).sum())
    ticket_data = ticket_data.loc[closed].copy()

    if scope == "ti":
        catalogs = ticket_data.get(
            "services_catalog_name", pd.Series("", index=ticket_data.index)
        ).map(normalize_text)
        mask = catalogs.map(lambda value: any(term in value for term in TI_TERMS))
        report["excluidos_fora_escopo"] = int((~mask).sum())
        ticket_data = ticket_data.loc[mask].copy()
    else:
        report["excluidos_fora_escopo"] = 0

    appointment_data = appointment_data.loc[appointment_data.ticket_id.isin(ticket_data.id)].copy()
    appointment_data["clean"] = appointment_data.description.map(clean_text)
    risky = set(appointment_data.loc[appointment_data.clean.map(sensitive), "ticket_id"])
    date_column = next(
        (column for column in ("created_at", "date", "beginning") if column in appointment_data),
        None,
    )
    if date_column:
        appointment_data["_time"] = pd.to_datetime(
            appointment_data[date_column], errors="coerce", utc=True
        )
        appointment_data = appointment_data.sort_values(
            ["_time", "id"], kind="stable", na_position="last"
        )

    notes: dict[str, list[str]] = {}
    note_ids: dict[str, list[str]] = {}
    for row in appointment_data.to_dict("records"):
        ticket_id = row["ticket_id"]
        if ticket_id in risky:
            continue
        value = sanitize(row["clean"], names)
        normalized = normalize_text(value).strip(" .!")
        is_survey = (
            "avali" in normalized
            and "atendimento" in normalized
            and ("agradec" in normalized or "pesquisa" in normalized)
        )
        if not value or normalized in GENERIC or is_survey:
            report["mensagens_genericas_removidas"] += 1
            continue
        notes.setdefault(ticket_id, []).append(value)
        note_ids.setdefault(ticket_id, []).append(row["id"])

    rows: list[dict] = []
    for row in ticket_data.to_dict("records"):
        if row["id"] in risky or sensitive(row["title"] + " " + row["description"]):
            report["excluidos_sensiveis"] += 1
            continue
        title = sanitize(row["title"], names)
        description = sanitize(row["description"], names)
        if not title and not description:
            continue
        search_text = f"Assunto: {title} Descricao: {description}"
        limited = len(search_text) > 6000
        if limited:
            report["textos_limitados"] += 1
        rows.append(
            {
                "ticket_id": row["id"],
                "ticket_number": row["ticket_number"],
                "title": title,
                "description": description,
                "created_at": row.get("created_at", ""),
                "catalogo": row.get("services_catalog_name", ""),
                "area": row.get("services_catalogs_area_name", ""),
                "item": row.get("services_catalogs_item_name", ""),
                "mesa": row.get("desk_name", ""),
                "texto_busca": search_text[:6000],
                "texto_limitado": str(limited).lower(),
                "historico_atendimento": "\n".join(notes.get(row["id"], [])),
                "apontamento_ids": ",".join(note_ids.get(row["id"], [])),
                "status_conhecimento": "HISTORICO_NAO_VALIDADO",
            }
        )
    if not rows:
        raise ValueError("Nenhum registro restou apos filtros. Confira o escopo.")
    output = pd.DataFrame(rows)
    report["registros_preparados"] = len(output)
    report["com_historico"] = int(output.historico_atendimento.ne("").sum())
    report["limite_caracteres_texto_busca"] = 6000
    report["privacidade"] = (
        "Mascaramento parcial por regras. Revisao humana obrigatoria antes de exibir."
    )
    return output, report
