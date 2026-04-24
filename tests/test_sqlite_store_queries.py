"""Tests for SqliteStore field and pesticide query methods."""
from __future__ import annotations

from modules.infra.sqlite_store import SqliteStore


def test_count_fields_returns_zero_when_empty(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        assert store.count_fields() == 0
    finally:
        store.close()


def test_count_fields_returns_correct_count(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
            }
        )
        store.upsert_field(
            {
                "field_id": "field-002",
                "field_name": "测试田2",
                "city": "开封市",
            }
        )
        assert store.count_fields() == 2
    finally:
        store.close()


def test_field_exists_returns_true_when_present(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
            }
        )
        assert store.field_exists("field-001") is True
        assert store.field_exists("non-existent") is False
    finally:
        store.close()


def test_field_exists_returns_false_when_absent(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        assert store.field_exists("non-existent") is False
    finally:
        store.close()


def test_get_field_source_returns_source_when_present(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
                "source": "user_upload",
            }
        )
        assert store.get_field_source("field-001") == "user_upload"
    finally:
        store.close()


def test_get_field_source_returns_none_when_absent(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
            }
        )
        assert store.get_field_source("field-001") is None
    finally:
        store.close()


def test_get_field_source_returns_none_for_nonexistent_field(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        assert store.get_field_source("non-existent") is None
    finally:
        store.close()


def test_count_non_fallback_fields_counts_null_and_other_sources(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        # NULL source - should be counted
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
            }
        )
        # drone_config_fallback source - should NOT be counted
        store.upsert_field(
            {
                "field_id": "field-002",
                "field_name": "测试田2",
                "city": "开封市",
                "source": "drone_config_fallback",
            }
        )
        # other source - should be counted
        store.upsert_field(
            {
                "field_id": "field-003",
                "field_name": "测试田3",
                "city": "洛阳市",
                "source": "user_upload",
            }
        )
        assert store.count_non_fallback_fields() == 2
    finally:
        store.close()


def test_count_non_fallback_fields_returns_zero_when_only_fallback(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
                "source": "drone_config_fallback",
            }
        )
        assert store.count_non_fallback_fields() == 0
    finally:
        store.close()


def test_get_first_non_fallback_field_id_returns_first_by_city_and_name(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        # This should be first: city "A市" < "B市", field_name "A田" < "B田"
        store.upsert_field(
            {
                "field_id": "field-aaa",
                "field_name": "A测试田",
                "city": "A市",
                "source": "user_upload",
            }
        )
        store.upsert_field(
            {
                "field_id": "field-bbb",
                "field_name": "B测试田",
                "city": "B市",
                "source": "user_upload",
            }
        )
        store.upsert_field(
            {
                "field_id": "field-fallback",
                "field_name": "Fallback田",
                "city": "A市",
                "source": "drone_config_fallback",
            }
        )
        assert store.get_first_non_fallback_field_id() == "field-aaa"
    finally:
        store.close()


def test_get_first_non_fallback_field_id_includes_null_source(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        # NULL source should be included
        store.upsert_field(
            {
                "field_id": "field-null",
                "field_name": "Null田",
                "city": "A市",
            }
        )
        store.upsert_field(
            {
                "field_id": "field-fallback",
                "field_name": "Fallback田",
                "city": "B市",
                "source": "drone_config_fallback",
            }
        )
        assert store.get_first_non_fallback_field_id() == "field-null"
    finally:
        store.close()


def test_get_first_non_fallback_field_id_returns_none_when_only_fallback(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-fallback",
                "field_name": "Fallback田",
                "city": "郑州市",
                "source": "drone_config_fallback",
            }
        )
        assert store.get_first_non_fallback_field_id() is None
    finally:
        store.close()


def test_field_has_non_fallback_source_returns_true(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
                "source": "user_upload",
            }
        )
        assert store.field_has_non_fallback_source() is True
    finally:
        store.close()


def test_field_has_non_fallback_source_returns_true_for_null_source(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
            }
        )
        assert store.field_has_non_fallback_source() is True
    finally:
        store.close()


def test_field_has_non_fallback_source_returns_false_when_only_fallback(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "field-001",
                "field_name": "测试田1",
                "city": "郑州市",
                "source": "drone_config_fallback",
            }
        )
        assert store.field_has_non_fallback_source() is False
    finally:
        store.close()


def test_resolve_pesticide_id_by_name_returns_id(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "pest-001",
                "product_name": "吡虫啉",
                "active_ingredient": "imidacloprid",
            }
        )
        assert store.resolve_pesticide_id_by_name("吡虫啉") == "pest-001"
    finally:
        store.close()


def test_resolve_pesticide_id_by_name_returns_first_when_duplicates(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "pest-002",
                "product_name": "阿维菌素",
            }
        )
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "pest-001",
                "product_name": "阿维菌素",
            }
        )
        # Should return the one with smaller pesticide_id (pest-001)
        assert store.resolve_pesticide_id_by_name("阿维菌素") == "pest-001"
    finally:
        store.close()


def test_resolve_pesticide_id_by_name_returns_none_when_not_found(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    store = SqliteStore(db_path)
    try:
        assert store.resolve_pesticide_id_by_name("不存在的农药") is None
    finally:
        store.close()
