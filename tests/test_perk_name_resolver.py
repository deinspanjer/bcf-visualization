from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from perk_name_resolver import build_directory_match_index  # noqa: E402


def test_name_only_fallback_rejects_incompatible_explicit_context() -> None:
    index = build_directory_match_index(
        [
            {
                "id": "Personal Reality__Personal Reality__entrance hall",
                "name": "Entrance Hall",
                "jump": "Personal Reality",
                "constellation": "Personal Reality",
            }
        ],
        aliases={
            "Entrance Hall": ["Entrance Hall - Espirit de Kerbal"],
        },
    )

    assert index.lookup(
        "Espirit de Kerbal",
        jump="Kerbal Space Program",
        constellation="Vehicles",
    ) is None


def test_name_only_fallback_allows_jump_drift_within_constellation() -> None:
    directory_row = {
        "id": "Time__Fast and Furious__most holy order",
        "name": "Most Holy Order of the Socket Wrench",
        "jump": "Fast and Furious",
        "constellation": "Time",
    }
    index = build_directory_match_index(
        [directory_row],
        aliases={
            "Most Holy Order of the Socket Wrench": [
                "Most Holy Order of the Stocket Wrench"
            ],
        },
    )

    assert index.lookup(
        "Most Holy Order of the Stocket Wrench",
        jump="Fast and the Furious",
        constellation="Time",
    ) == directory_row


def test_name_only_fallback_keeps_same_constellation_alias_candidates() -> None:
    personal_reality_workshop = {
        "id": "Toolkits__Personal Reality__workshop",
        "name": "Workshop",
        "jump": "Personal Reality",
        "constellation": "Toolkits",
    }
    index = build_directory_match_index(
        [
            personal_reality_workshop,
            {
                "id": "Toolkits__Samurai Jack__workshop",
                "name": "Workshop",
                "jump": "Samurai Jack",
                "constellation": "Toolkits",
            },
        ],
        aliases={"Workshop": ["Workshop: Woodworking"]},
    )

    assert index.lookup(
        "Workshop: Woodworking",
        jump="Warehouse",
        constellation="Toolkits",
    ) == personal_reality_workshop
