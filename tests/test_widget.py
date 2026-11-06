from pathlib import Path

WIDGET = Path(__file__).resolve().parents[1] / "frontend" / "public" / "widget.js"


def test_the_widget_embeds_the_assistant_in_an_isolated_frame_without_external_code():
    js = WIDGET.read_text(encoding="utf-8")
    assert "createElement(\"iframe\")" in js and "aria-label" in js     # isolated frame, labelled launcher
    assert "http" not in js.replace("https://YOUR-ZALDI-HOST", "")     # it only ever talks to the host it was loaded from
    assert "document.cookie" not in js and "localStorage" not in js    # it never reads the host page's data
