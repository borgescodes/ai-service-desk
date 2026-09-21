"""Catálogo CDM independente da identidade; fornecido pelo boundary de integração."""

import re
from dataclasses import dataclass

from ai_service_desk.engine.validation import normalize_text


@dataclass(frozen=True)
class CDMBusinessScope:
    key: str
    label: str
    area_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CDMScopeCatalog:
    scopes: tuple[CDMBusinessScope, ...]

    def __post_init__(self):
        keys = [scope.key for scope in self.scopes]
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("Catálogo CDM exige escopos únicos.")
        aliases = {}
        for scope in self.scopes:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", scope.key) or not scope.label.strip():
                raise ValueError("Escopo CDM inválido.")
            for value in (scope.key, scope.label, *scope.area_aliases):
                normalized = normalize_text(value)
                if not normalized or aliases.get(normalized, scope.key) != scope.key:
                    raise ValueError("Alias CDM ambíguo.")
                aliases[normalized] = scope.key

    def match_area(self, area: str) -> str | None:
        normalized = normalize_text(area)
        for scope in self.scopes:
            if normalized in {
                normalize_text(v) for v in (scope.key, scope.label, *scope.area_aliases)
            }:
                return scope.key
        return None

    def requested_scope(self, text: str) -> tuple[bool, str | None]:
        normalized = normalize_text(text)
        matches = set()
        for scope in self.scopes:
            for value in (scope.key, scope.label):
                pattern = (
                    r"\b(?:para|no escopo|na area) (?:a |o |uma |um )?"
                    rf"{re.escape(normalize_text(value))}\b"
                )
                if re.search(pattern, normalized):
                    matches.add(scope.key)
        if matches:
            # Não interpretar negação ou múltiplos escopos como intenção confirmada.
            if len(matches) != 1 or re.search(r"\bnao\b", normalized):
                return True, None
            return True, next(iter(matches))
        target = re.search(
            r"\b(?:cdm|central de dados mestres) para (?:a |o |uma |um )?([a-z0-9]+)\b", normalized
        )
        if target and target.group(1) not in {
            "mim",
            "solicitar",
            "cadastrar",
            "criar",
            "pedir",
            "acessar",
            "trabalhar",
            "aprovar",
        }:
            return True, None
        return False, None

    def system_text(self, text: str) -> str:
        normalized = normalize_text(text)
        if not re.search(r"\b(?:cdm|central de dados mestres)\b", normalized):
            return text
        for scope in self.scopes:
            for value in (scope.key, scope.label):
                value = re.escape(normalize_text(value))
                normalized = re.sub(
                    rf"\b(?:para|no escopo|na area) (?:a |o |uma |um )?{value}\b", "", normalized
                )
                normalized = re.sub(rf"\bminha area (?:agora )?e {value}\b", "", normalized)
        return normalized

    def label(self, key: str) -> str:
        return next(scope.label for scope in self.scopes if scope.key == key)


LOCAL_CDM_SCOPE_CATALOG = CDMScopeCatalog(
    (
        CDMBusinessScope("revenda", "Revenda", ("Revenda - Matriz",)),
        CDMBusinessScope("ubs", "UBS"),
        CDMBusinessScope("fazenda", "Fazenda"),
    )
)
