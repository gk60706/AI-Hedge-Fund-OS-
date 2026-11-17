from ai_team.source_extraction import (
    extract_sources_from_content,
    extract_sources_or_empty,
)


def test_prefers_last_json_fence():
    content = '''```json
{"sources": [{"name": "first"}]}
JSON
{"sources": [{"name": "second"}]}
```'''
    assert extract_sources_from_content(content) == [{"name": "second"}]


def test_bare_json_object_is_extracted():
    content = 'Report: {"sources": [{"name": "example"}]} End.'
    assert extract_sources_from_content(content) == [{"name": "example"}]


def test_bare_array_is_extracted():
    content = 'Sources: [{"name": "example"}] End.'
    assert extract_sources_from_content(content) == [{"name": "example"}]


def test_non_dict_items_are_dropped():
    content = '[{"name": "example"}, 42, "x"]'
    assert extract_sources_from_content(content) == [{"name": "example"}]


def test_no_json_returns_none():
    content = "This report contains no structured sources."
    assert extract_sources_from_content(content) is None
    assert extract_sources_or_empty(content) == []


def test_malformed_json_returns_none():
    content = '```json\n{"sources": [invalid]}\n```'
    assert extract_sources_from_content(content) is None
