import json
from pathlib import Path

from ai_service_desk.engine.learning_prevention import OutcomeRecord

_REVIEWED_AT = "2026-09-09T12:00:00-03:00"
_M365_REVIEWED_AT = "2026-09-11T09:44:00-03:00"


def _write_jsonl(path: str | Path, rows: list[dict]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return target


def write_demo_knowledge(path: str | Path) -> Path:
    return _write_jsonl(
        path,
        [
            {
                "knowledge_id": "KB-SYN-CDM-ACCESS-001",
                "title": "Acesso ao CDM para solicitação de materiais",
                "question": "Como solicitar acesso ao CDM para pedir materiais para uma revenda?",
                "answer": (
                    "O acesso de solicitante ao CDM precisa de aprovação humana antes da liberação."
                ),
                "system": "CDM",
                "intent": "PROBLEMA_ACESSO",
                "tags": ["acesso", "materiais", "revenda"],
                "source": "SYNTHETIC_DEMO",
                "status": "APPROVED",
                "reviewed_by": "DEMO-REVIEWER",
                "reviewed_at": _REVIEWED_AT,
                "version": 1,
            },
            {
                "knowledge_id": "KB-SYN-M365-PASSWORD-001",
                "title": "Recuperar acesso ao Microsoft 365",
                "question": "O que fazer quando não consigo acessar o Microsoft 365 por senha?",
                "answer": (
                    "Vamos redefinir sua senha do Microsoft 365.\n\n"
                    "1. Acesse a página de redefinição de senha da Microsoft.\n"
                    "2. Informe seu e-mail corporativo e conclua a verificação exibida na tela.\n"
                    "3. Clique em Avançar.\n"
                    "4. Escolha um dos métodos de confirmação de identidade disponíveis para "
                    "sua conta, como Microsoft Authenticator, SMS, telefone ou outro método "
                    "cadastrado.\n"
                    "5. Confirme sua identidade usando o código ou a solicitação recebida.\n"
                    "6. Crie uma nova senha seguindo os requisitos apresentados.\n"
                    "7. Depois da alteração, tente entrar novamente no Outlook, Teams e demais "
                    "aplicativos do Microsoft 365.\n\n"
                    "Faça esse procedimento e me diga se conseguiu acessar."
                ),
                "system": "OFFICE 365",
                "intent": "PROBLEMA_ACESSO",
                "tags": ["acesso", "senha", "microsoft-365"],
                "source": "SYNTHETIC_DEMO",
                "status": "APPROVED",
                "reviewed_by": "DEMO-REVIEWER",
                "reviewed_at": _M365_REVIEWED_AT,
                "version": 2,
            },
        ],
    )


def write_demo_playbooks(path: str | Path) -> Path:
    return _write_jsonl(
        path,
        [
            {
                "playbook_id": "PB-SYN-CDM-ACCESS-001",
                "title": "Solicitar acesso controlado ao CDM",
                "description": "Propõe a solicitação de acesso mínimo ao CDM.",
                "knowledge_ids": ["KB-SYN-CDM-ACCESS-001"],
                "steps": [
                    {
                        "step_id": "STEP-CDM-ACCESS-01",
                        "type": "ACTION_PROPOSAL",
                        "title": "Solicitar acesso de solicitante",
                        "instruction": (
                            "Criar solicitação controlada de acesso ao CDM para o perfil "
                            "SOLICITANTE."
                        ),
                        "capability": "CDM_ACCESS_REQUEST",
                    }
                ],
                "source": "SYNTHETIC_DEMO",
                "status": "APPROVED",
                "reviewed_by": "DEMO-REVIEWER",
                "reviewed_at": _REVIEWED_AT,
                "version": 1,
            }
        ],
    )


def demo_outcomes() -> tuple[OutcomeRecord, ...]:
    return tuple(
        OutcomeRecord(
            interaction_id=f"DEMO-PREVENTION-{index:03d}",
            system="OFFICE 365",
            intent="PROBLEMA_ACESSO",
            capability="",
            area="Comercial",
            knowledge_id="KB-SYN-M365-PASSWORD-001",
            playbook_id="",
            playbook_version=None,
            step_id="",
            outcome="RESOLVED_BY_KNOWLEDGE",
            reason_code="",
        )
        for index in range(1, 5)
    )
