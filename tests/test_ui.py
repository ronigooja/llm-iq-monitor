from llm_iq_monitor.ui import sanitize_svg


def test_sanitize_svg_benign_and_fenced_last_wins():
    svg, valid = sanitize_svg("old <svg><script/></svg> ```xml\n<svg viewBox='0 0 1 1'><path d='M0 0'/></svg>\n```")
    assert valid and svg.startswith("<svg ") and 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert "path" in svg and "script" not in svg


def test_sanitize_svg_rejections():
    bad = [
        "<svg><script/></svg>",
        "<svg><foreignObject/></svg>",
        "<svg><iframe/></svg>",
        "<svg><object/></svg>",
        "<svg><embed/></svg>",
        "<svg><audio/></svg>",
        "<svg><video/></svg>",
        "<svg><animate attributeName='href'/></svg>",
        "<svg><set attributeName='href'/></svg>",
        "<svg onload='x'/>",
        "<svg><a href='https://example.com'/></svg>",
        "<svg style='background:url(https://example.com/a)'/>",
        "<svg><style>@import url(https://example.com/a)</style></svg>",
        "<!DOCTYPE svg [<!ENTITY x 'x'>]><svg>&x;</svg>",
        "reply without svg",
    ]
    for reply in bad:
        assert sanitize_svg(reply) == (None, False), reply


def test_sanitize_svg_oversize():
    assert sanitize_svg("<svg>" + ("x" * (200 * 1024)) + "</svg>") == (None, False)
