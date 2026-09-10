"""Vocabulário vigente da demo; não contém procedimentos ou autoridade operacional."""

import re
from dataclasses import dataclass

from ai_service_desk.engine.classification import SYSTEM_ALIASES
from ai_service_desk.engine.validation import normalize_text


@dataclass(frozen=True)
class BusinessSystem:
    name: str
    aliases: tuple[str, ...]
    meaning: str
    temporal: str = "CURRENT"
    related: tuple[str, ...] = ()


SYSTEMS = (
    BusinessSystem(
        "OFFICE 365",
        ("Office", "Office 365", "Office365", "Microsoft 365", "M365"),
        "Suíte Microsoft 365; Outlook, Teams e OneDrive são produtos da mesma suíte.",
    ),
    BusinessSystem(
        "SIAGRI",
        ("SIAGRI", "SIAGRI Agribusiness", "SIAGRI ERP Agribusiness"),
        "ERP legado do negócio agrícola, ainda ativo durante a transição para SAP.",
        "LEGACY_ACTIVE",
        ("SAP",),
    ),
    BusinessSystem(
        "CIGAM 11",
        ("CIGAM", "CIGAM 11", "Cigan"),
        "Sistema administrativo distinto do SIAGRI, relacionado a METADADOS e Portal RH.",
        "LEGACY_ACTIVE",
        ("METADADOS", "PORTAL RH", "SAP"),
    ),
    BusinessSystem(
        "METADADOS",
        ("METADADOS",),
        "Aplicação de Recursos Humanos e Departamento Pessoal.",
        related=("CIGAM 11", "PORTAL RH"),
    ),
    BusinessSystem(
        "PORTAL RH",
        ("Portal RH", "PortalRH"),
        "Interface de serviços e informações de RH para colaboradores.",
        related=("METADADOS", "CIGAM 11"),
    ),
    BusinessSystem(
        "SAP",
        ("SAP", "SAP S/4HANA", "S/4HANA"),
        "Novo ERP em implantação. Coexiste com SIAGRI e CIGAM 11. "
        "Processo previsto para migração não significa função liberada em produção.",
        "TRANSITIONING",
        ("SIAGRI", "CIGAM 11", "CDM"),
    ),
    BusinessSystem(
        "CDM",
        ("CDM", "Central de Dados Mestres"),
        "Governa solicitações de cadastro de materiais antes da constituição no SAP. "
        "Organiza modelos, revisão, correções e aprovação quando aplicável, e acompanha "
        "a integração. O escopo atual é de insumos agrícolas para revenda. "
        "Não substitui SAP como sistema mestre. Comprar ou pedir material não identifica CDM.",
        related=("SAP",),
    ),
)
PRODUCTS = (
    ("OUTLOOK", ("Outlook",)),
    ("TEAMS", ("Teams",)),
    ("ONEDRIVE", ("OneDrive", "One Drive")),
)
# Cigan: candidato HISTORICAL_LANGUAGE_ONLY, 62 registros em título/descrição;
# correspondência com CIGAM revisada nesta etapa. Não importa procedimentos.
CONTEXT_VERSION = "2026-09-10"
PROVENANCE = "BUSINESS_CONTEXT_CURRENT"


def _contains(text: str, value: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(normalize_text(value))}(?!\w)", text) is not None


@dataclass(frozen=True)
class BusinessVocabulary:
    def aliases(self, system: str) -> tuple[str, ...]:
        for entry in SYSTEMS:
            if entry.name == system:
                products = tuple(alias for _, aliases in PRODUCTS for alias in aliases)
                return entry.aliases + (products if system == "OFFICE 365" else ())
        return SYSTEM_ALIASES.get(system, (system,))

    def canonical(self, value: str) -> str | None:
        normalized = normalize_text(value)
        for entry in SYSTEMS:
            if any(normalized == normalize_text(alias) for alias in self.aliases(entry.name)):
                return entry.name
        for name, aliases in SYSTEM_ALIASES.items():
            if normalized in {normalize_text(name), *(normalize_text(a) for a in aliases)}:
                return name
        return None

    def systems(self, text: str) -> tuple[str, ...]:
        normalized = normalize_text(text)
        candidates = [entry.name for entry in SYSTEMS]
        candidates.extend(name for name in SYSTEM_ALIASES if self.canonical(name) == name)
        matches = tuple(
            dict.fromkeys(
                name
                for name in candidates
                if any(_contains(normalized, alias) for alias in self.aliases(name))
            )
        )
        if matches:
            return matches
        # A conjunção deve ocorrer na mesma oração; negação impede inferência.
        for clause in re.split(r"[.!?;\n]", normalized):
            if re.search(r"\b(nao|nunca|sem)\b", clause):
                continue
            if re.search(
                r"\b(?:cadastrar|cadastro|cadastramento|criar|criacao)\b"
                r"[^.!?;\n]{0,80}\b(?:material|materiais)\b"
                r"[^.!?;\n]{0,40}\bpara\s+(?:a\s+)?revenda\b",
                clause,
            ):
                return ("CDM",)
        return ()

    def entities(self, text: str) -> dict[str, str]:
        normalized = normalize_text(text)
        products = [
            name
            for name, aliases in PRODUCTS
            if any(_contains(normalized, alias) for alias in aliases)
        ]
        return {"product": ", ".join(products)}

    def prompt(self) -> str:
        lines = [f"{PROVENANCE}; versão {CONTEXT_VERSION}. Contexto linguístico curado."]
        for entry in SYSTEMS:
            lines.append(
                f"{entry.name}: aliases {', '.join(entry.aliases)}. "
                f"{entry.meaning} Situação: {entry.temporal}."
            )
        lines.extend(
            [
                "Portal RH, METADADOS e CIGAM 11 não são a mesma aplicação. "
                "Relação não significa equivalência.",
                "Cadastro de material para revenda é contexto forte CDM; compra, pedido e "
                "movimentação não bastam. Sistema explícito prevalece. "
                "Não inferir SAP por migração.",
                "Cadastro de dados de negócio cria registros, não instala programas. "
                "INSTALACAO_SOFTWARE exige uma necessidade de instalar aplicativo ou programa, "
                "não criar cadastros. Pedidos de processo de negócio fora das categorias de TI "
                "são OUTRO; dúvidas sobre como fazer são ORIENTACAO. "
                "O sistema mencionado não determina a intenção.",
                "Use esse contexto para compreender a mensagem, preservando produto e intenção. "
                "Reconhecer sistema não implica orientação aprovada ou capacidade de ação. "
                "Não converta cadastro em problema de acesso. Identidade, decisões e execução "
                "pertencem exclusivamente ao backend. Não crie nem declare fatos operacionais.",
            ]
        )
        return "\n".join(lines)
