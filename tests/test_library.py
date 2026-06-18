from letmesee.library import Library


def _rec(rid, **kw):
    base = {"id": rid, "title": "", "absorbed_at": rid}
    base.update(kw)
    return base


def test_add_get_has(tmp_path):
    lib = Library(tmp_path / "lib")
    assert not lib.has("a")
    lib.add(_rec("a", title="Hello World"))
    assert lib.has("a")
    assert lib.get("a")["title"] == "Hello World"
    assert lib.get("missing") is None


def test_index_persists_across_instances(tmp_path):
    root = tmp_path / "lib"
    Library(root).add(_rec("a", title="Persisted"))
    assert Library(root).get("a")["title"] == "Persisted"


def test_all_sorted_by_absorbed_at_desc(tmp_path):
    lib = Library(tmp_path / "lib")
    lib.add(_rec("a", absorbed_at="2024-01-01"))
    lib.add(_rec("b", absorbed_at="2024-03-01"))
    lib.add(_rec("c", absorbed_at="2024-02-01"))
    assert [r["id"] for r in lib.all()] == ["b", "c", "a"]


def test_search_across_fields_and_transcript(tmp_path):
    lib = Library(tmp_path / "lib")
    lib.add(_rec("a", title="Cooking pasta", transcript="boil the water"))
    lib.add(_rec("b", title="Guitar lesson", uploader="MusicPro"))
    lib.add(_rec("c", title="Random", tags=["pasta", "italian"]))

    assert {r["id"] for r in lib.search("pasta")} == {"a", "c"}
    assert {r["id"] for r in lib.search("water")} == {"a"}
    assert {r["id"] for r in lib.search("musicpro")} == {"b"}
    # Multiple terms must all match.
    assert {r["id"] for r in lib.search("cooking water")} == {"a"}
    # Empty query returns everything.
    assert len(lib.search("")) == 3


def test_item_dir_sanitises_id(tmp_path):
    lib = Library(tmp_path / "lib")
    d = lib.item_dir("ab/cd?ef")
    assert "/" not in d.name and "?" not in d.name


def test_corrupt_index_is_tolerated(tmp_path):
    root = tmp_path / "lib"
    lib = Library(root)
    lib.index_path.write_text("{ not json", encoding="utf-8")
    assert lib.all() == []
    lib.add(_rec("a"))
    assert lib.has("a")
