from scripts.scaffold_constellation_pages import (
    GENERATED_BANNER,
    jumps_for,
    perks_for,
    prefix_svg_ids,
    render_cluster_page,
    render_top_index,
    status_string,
)


def test_prefix_svg_ids_rewrites_id_decls_href_and_url_refs() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="ray-grad"/><symbol id="star-mark"/></defs>'
        '<rect fill="url(#ray-grad)"/>'
        '<use href="#star-mark"/>'
        "</svg>"
    )

    out = prefix_svg_ids(svg, "01-toolkits")

    assert 'id="01-toolkits-ray-grad"' in out
    assert 'id="01-toolkits-star-mark"' in out
    assert 'fill="url(#01-toolkits-ray-grad)"' in out
    assert 'href="#01-toolkits-star-mark"' in out
    # The original (unprefixed) ids must not survive
    assert 'id="ray-grad"' not in out
    assert 'href="#star-mark"' not in out
    assert 'url(#ray-grad)' not in out


def test_prefix_svg_ids_leaves_other_attributes_alone() -> None:
    svg = '<svg data-id_str="keep-me" aria-labelledby="title"><title id="title">x</title></svg>'

    out = prefix_svg_ids(svg, "07-magic")

    assert 'data-id_str="keep-me"' in out
    # The actual id="..." is rewritten, the aria-labelledby is left alone
    # (it isn't in our rewrite scope; consumers should not rely on it inside
    # inlined SVGs anyway).
    assert 'id="07-magic-title"' in out


def test_prefix_svg_ids_strips_xml_prolog() -> None:
    svg = '<?xml version="1.0"?>\n<svg><defs><linearGradient id="g"/></defs></svg>'

    out = prefix_svg_ids(svg, "12-alchemy")

    assert not out.startswith("<?xml")
    assert out.startswith("<svg>")
    assert 'id="12-alchemy-g"' in out


def test_jumps_for_sorts_by_perk_count_desc_then_name() -> None:
    perks = [
        {"constellation": "Toolkits", "jump": "Alpha", "name": "p1", "cost": 100},
        {"constellation": "Toolkits", "jump": "Beta", "name": "p2", "cost": 100},
        {"constellation": "Toolkits", "jump": "Beta", "name": "p3", "cost": 200},
        {"constellation": "Other", "jump": "Beta", "name": "px", "cost": 100},
    ]

    jumps = jumps_for("Toolkits", perks)

    assert [j["name"] for j in jumps] == ["Beta", "Alpha"]
    assert [len(j["perks"]) for j in jumps] == [2, 1]


def test_perks_for_sorts_by_jump_alpha_then_cost_desc() -> None:
    perks = [
        {"constellation": "Toolkits", "jump": "Beta", "name": "b1", "cost": 100},
        {"constellation": "Toolkits", "jump": "Alpha", "name": "a1", "cost": 200},
        {"constellation": "Toolkits", "jump": "Alpha", "name": "a2", "cost": 400},
        {"constellation": "Toolkits", "jump": "Alpha", "name": "a3", "cost": None},
    ]

    out = perks_for("Toolkits", perks)

    assert [(p["jump"], p["name"]) for p in out] == [
        ("Alpha", "a2"),
        ("Alpha", "a1"),
        ("Alpha", "a3"),
        ("Beta", "b1"),
    ]


def test_status_string_marks_incomplete_when_no_completed_chapter() -> None:
    assert status_string({"revealed_at_chapter": "1", "completed_at_chapter": None}) == "revealed ch 1 · incomplete"
    assert status_string({"revealed_at_chapter": "1", "completed_at_chapter": "97"}) == "revealed ch 1 · completed ch 97"


def test_render_cluster_page_inlines_prefixed_svg_and_workbench_link() -> None:
    cluster = {
        "name": "Toolkits",
        "slug": "01-toolkits",
        "slot_position": 1,
        "revealed_at_chapter": "1",
        "completed_at_chapter": None,
        "entered_pool_at_chapter": "1",
    }
    metadata = {"intended_image": "toolbox: open box with a hammer"}
    svg_inline = '<svg><defs><linearGradient id="01-toolkits-g"/></defs></svg>'
    jumps = [{"name": "GUNNM", "perks": [{"name": "Workshop"}]}]
    perks = [{"jump": "GUNNM", "name": "Workshop", "cost": 100}]

    rendered = render_cluster_page(
        cluster=cluster, metadata=metadata, svg_inline=svg_inline, jumps=jumps, perks=perks
    )

    assert GENERATED_BANNER in rendered
    assert "<title>Toolkits · Constellation</title>" in rendered
    assert "01 · Toolkits" in rendered
    assert "toolbox: open box with a hammer" in rendered
    assert '../tracing-workbench.html?constellation=01-toolkits' in rendered
    assert '../index.html' in rendered
    assert svg_inline in rendered
    assert "<td>GUNNM</td>" in rendered
    assert "100 CP" in rendered


def test_render_cluster_page_handles_completed_chapter() -> None:
    cluster = {
        "name": "Time",
        "slug": "04-time",
        "slot_position": 4,
        "revealed_at_chapter": "3",
        "completed_at_chapter": "113",
        "entered_pool_at_chapter": "3",
    }
    rendered = render_cluster_page(
        cluster=cluster,
        metadata={"intended_image": "hourglass"},
        svg_inline="<svg/>",
        jumps=[],
        perks=[],
    )

    assert "<dd>113</dd>" in rendered


def test_render_top_index_lists_records_in_slot_order_with_unique_ids() -> None:
    records = [
        {
            "cluster": {
                "name": "Toolkits",
                "slug": "01-toolkits",
                "slot_position": 1,
                "revealed_at_chapter": "1",
                "completed_at_chapter": None,
                "entered_pool_at_chapter": "1",
            },
            "svg_inline": '<svg><defs><linearGradient id="01-toolkits-g"/></defs></svg>',
            "jump_count": 24,
            "perk_count": 27,
        },
        {
            "cluster": {
                "name": "Knowledge",
                "slug": "02-knowledge",
                "slot_position": 2,
                "revealed_at_chapter": "4",
                "completed_at_chapter": None,
                "entered_pool_at_chapter": "4",
            },
            "svg_inline": '<svg><defs><linearGradient id="02-knowledge-g"/></defs></svg>',
            "jump_count": 18,
            "perk_count": 47,
        },
    ]

    rendered = render_top_index(records)

    assert GENERATED_BANNER in rendered
    assert '<a href="01-toolkits/index.html">Toolkits</a>' in rendered
    assert '<a href="02-knowledge/index.html">Knowledge</a>' in rendered
    assert 'tracing-workbench.html?constellation=01-toolkits' in rendered
    assert 'tracing-workbench.html?constellation=02-knowledge' in rendered
    # ids are unique on the page (the inlined SVGs ship pre-prefixed)
    assert rendered.count('id="01-toolkits-g"') == 1
    assert rendered.count('id="02-knowledge-g"') == 1
