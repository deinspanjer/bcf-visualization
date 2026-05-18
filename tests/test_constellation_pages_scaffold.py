from scripts.scaffold_constellation_pages import build_free_addons, page_html, root_index_html


def test_free_addons_attach_to_each_paid_perk_in_multi_grab_roll() -> None:
    jumps = [
        {
            "constellation": "Toolkits",
            "jump": "GUNNM",
            "stars": [
                {"perk_name": "Civilian Equipment Package", "cost": 100},
                {"perk_name": "Cyber-doctor Equipment Package", "cost": 200},
            ],
        }
    ]
    rolls = [
        {
            "constellation": "Toolkits",
            "purchased_perk_jump": "GUNNM",
            "purchased_perks": [
                {"name": "Civilian Equipment Package"},
                {"name": "Cyber-doctor Equipment Package"},
            ],
            "free_perks": [
                {"name": "Heirloom Weapon", "jump": "GUNNM/Battle Angel Alita"},
                {"name": "Rocket Hammer", "jump": "GUNNM/Battle Angel Alita"},
            ],
        }
    ]

    addons, unresolved = build_free_addons(jumps, rolls)

    assert unresolved == []
    assert addons[("Toolkits", "GUNNM", "Civilian Equipment Package")] == [
        "Heirloom Weapon",
        "Rocket Hammer",
    ]
    assert addons[("Toolkits", "GUNNM", "Cyber-doctor Equipment Package")] == [
        "Heirloom Weapon",
        "Rocket Hammer",
    ]


def test_free_addons_can_resolve_supplement_rolls_to_canonical_jump() -> None:
    jumps = [
        {
            "constellation": "Toolkits",
            "jump": "Personal Reality",
            "stars": [{"perk_name": "Workshop", "cost": 100}],
        }
    ]
    rolls = [
        {
            "constellation": "Toolkits",
            "purchased_perk_jump": "Personal Reality Supplement",
            "purchased_perks": [{"name": "Workshop"}],
            "free_perks": [
                {"name": "Access Key", "jump": "Personal Reality"},
                {"name": "Entrance Hall", "jump": "Personal Reality"},
            ],
        }
    ]

    addons, unresolved = build_free_addons(jumps, rolls)

    assert unresolved == []
    assert addons[("Toolkits", "Personal Reality", "Workshop")] == [
        "Access Key",
        "Entrance Hall",
    ]


def test_free_addons_resolve_paid_perk_when_roll_constellation_is_drifted() -> None:
    jumps = [
        {
            "constellation": "Crafting",
            "jump": "Bloodborne",
            "stars": [{"perk_name": "Workshop Artisan", "cost": 300}],
        }
    ]
    rolls = [
        {
            "constellation": "Personal Reality",
            "purchased_perk_jump": "Bloodborne",
            "purchased_perks": [{"name": "Workshop Artisan"}],
            "free_perks": [{"name": "Hunter", "jump": "Bloodborne", "constellation": "Crafting"}],
        }
    ]

    addons, unresolved = build_free_addons(jumps, rolls)

    assert unresolved == []
    assert addons[("Crafting", "Bloodborne", "Workshop Artisan")] == ["Hunter"]


def test_page_html_has_requested_tables_without_below_svg_caption() -> None:
    cluster = {
        "name": "Toolkits",
        "shape_concept": "open-end wrench",
    }
    jumps = [
        {
            "constellation": "Toolkits",
            "jump": "GUNNM",
            "stars": [{"perk_name": "Civilian Equipment Package", "cost": 100}],
        }
    ]
    addons = {
        ("Toolkits", "GUNNM", "Civilian Equipment Package"): ["Heirloom Weapon"],
    }

    rendered = page_html(
        cluster,
        jumps,
        "<!-- EDITABLE: cluster silhouette --><svg></svg><!-- /EDITABLE -->",
        addons,
        has_reference=True,
    )

    assert "<figcaption" not in rendered
    assert '<div class="preview-label">Current</div>' in rendered
    assert '<div class="preview-label">Reference</div>' in rendered
    assert '<img class="reference-image" src="reference.svg" alt="Toolkits reference image"/>' in rendered
    assert "<th>Jump name</th><th>Total perks in jump</th><th>Notes</th>" in rendered
    assert '<td class="note-field"></td>' in rendered
    assert "<tr><th>Perk name</th><th>Cost</th><th>Free add-ons</th></tr>" in rendered
    assert "<td>Heirloom Weapon</td>" in rendered
    assert '<a class="back-link" href="../index.html">Back to constellation index</a>' in rendered


def test_root_index_links_constellation_pages_in_order() -> None:
    page_records = [
        {
            "index": 1,
            "cluster": {"name": "Toolkits", "shape_concept": "open-end wrench"},
            "folder": "01-toolkits",
            "jumps": [{"jump": "GUNNM", "stars": [{"perk_name": "Workshop"}]}],
            "has_reference": True,
        },
        {
            "index": 2,
            "cluster": {"name": "Knowledge", "shape_concept": "open book"},
            "folder": "02-knowledge",
            "jumps": [
                {
                    "jump": "Halo",
                    "stars": [{"perk_name": "Engineer"}, {"perk_name": "Erudition"}],
                }
            ],
            "has_reference": False,
        },
    ]

    rendered = root_index_html(page_records)

    assert '<a href="01-toolkits/index.html">Toolkits</a>' in rendered
    assert '<a href="02-knowledge/index.html">Knowledge</a>' in rendered
    assert 'src="01-toolkits/current.svg"' in rendered
    assert 'class="thumb reference-thumb" src="01-toolkits/reference.svg"' in rendered
    assert '<span class="empty-thumb">none</span>' in rendered
    assert "<tr><th>Order</th><th>Constellation</th><th>Current</th><th>Reference</th><th>Jumps</th><th>Perks</th><th>Intended image</th></tr>" in rendered
