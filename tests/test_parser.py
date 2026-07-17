import pytest
from app.parser import parse_markdown

def test_duplicate_headings_are_distinct_and_correctly_parented():
    nodes = parse_markdown("# Manual\n## Safety\n### Warning\nFirst\n### Warning\nSecond")
    warnings = [n for n in nodes if n.heading == "Warning"]
    assert len(warnings) == 2
    assert warnings[0].identity_path != warnings[1].identity_path
    assert all(w.parent.heading == "Safety" for w in warnings)

def test_skipped_heading_attaches_to_nearest_lower_level():
    nodes = parse_markdown("# Manual\n## Operation\n##### Cuff\nText\n## Storage\nText")
    cuff = next(n for n in nodes if n.heading == "Cuff")
    assert cuff.level == 5
    assert cuff.parent.heading == "Operation"

def test_setext_heading_and_fenced_fake_heading():
    nodes = parse_markdown("# Manual\n## Errors\nError reference\n---------------\nBody\n```\n## Not heading\n```")
    assert [n.heading for n in nodes] == ["Manual", "Errors", "Error reference"]
    assert "## Not heading" in nodes[-1].body

def test_rejects_ambiguous_preamble():
    with pytest.raises(ValueError, match="before first heading"):
        parse_markdown("orphan text\n# Manual")

def test_rejects_unclosed_fence_instead_of_hiding_later_sections():
    with pytest.raises(ValueError, match="Unclosed fenced"):
        parse_markdown("# Manual\n```text\nexample\n## Hidden section\nBody")
