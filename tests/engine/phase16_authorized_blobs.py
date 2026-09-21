"""Extensões autorizadas pela Task 2: escopo, confirmação e transporte fake CDM.

Mantém hashes exatos, incluindo a identidade configurável da Task 1. Os arquivos
alterados são verificados no working tree para valer antes e depois do commit.
"""

PHASE16_AUTHORIZED_EXTENSIONS = {
    "src/ai_service_desk/engine/access_request.py": (
        "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
        "2ff714f7ff022683be02722fa3ff628f61c31dfb",
    ),
    "src/ai_service_desk/engine/policy.py": (
        "60a4f3ae785353009c30b37f71e1ce91865b899e",
        "0a9c134fa68d0c87b5b2ebfab184fe361df5c817",
    ),
    "src/ai_service_desk/engine/cdm_execution.py": (
        "516e258f2349fee42dbd963a7371d2ca3937ca69",
        "94c4aadfa2999d94b2de874a0a33361fc3e8f1ac",
    ),
    "src/ai_service_desk/integrations/cdm.py": (
        "83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe",
        "b4e6dde9edaa940afd231472c7c6bf566bf8cf8e",
    ),
    "src/ai_service_desk/integrations/cdm_fake_api.py": (
        "275b1833d5b27b09c0ffeae9f4484636d10afe63",
        "9f31ea39b5c3399b25b9847f8610b0b399ecf9ca",
    ),
}
