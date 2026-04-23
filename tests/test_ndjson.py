from pathlib import Path

import pytest

from evm_log_extractor.ndjson import NdjsonWriter, read_ndjson


def test_writer_writes_one_object_per_line(tmp_path: Path):
    out = tmp_path / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
        w.write({"b": 2})
    assert out.read_text() == '{"a": 1}\n{"b": 2}\n'


def test_writer_rejects_non_dict(tmp_path: Path):
    with NdjsonWriter(tmp_path / "o.ndjson") as w:
        with pytest.raises(TypeError):
            w.write([1, 2, 3])


def test_writer_tracks_count_and_sha256(tmp_path: Path):
    out = tmp_path / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
        w.write({"b": 2})
    assert w.count == 2
    import hashlib

    expected = hashlib.sha256(b'{"a": 1}\n{"b": 2}\n').hexdigest()
    assert w.sha256 == expected


def test_read_ndjson_streams_records(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
    records = list(read_ndjson(p))
    assert records == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_read_ndjson_skips_blank_lines(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\n\n{"b": 2}\n')
    assert list(read_ndjson(p)) == [{"a": 1}, {"b": 2}]


def test_read_ndjson_raises_on_malformed(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\nnot json\n')
    with pytest.raises(ValueError, match="line 2"):
        list(read_ndjson(p))


def test_writer_creates_parent_dirs(tmp_path: Path):
    out = tmp_path / "nested" / "deep" / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
    assert out.exists()

