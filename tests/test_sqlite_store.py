from modules.infra.sqlite_store import SqliteStore, utc_now_iso
from modules.infra.sqlite_store.agri_data import AgriDataMixin
from modules.infra.sqlite_store.base import BaseMixin, _SCHEMA_SQL
from modules.infra.sqlite_store.catalog import CatalogMixin
from modules.infra.sqlite_store.field import FieldMixin
from modules.infra.sqlite_store.task import TaskMixin


def test_sqlite_store_package_exports_mixin_composition() -> None:
    assert issubclass(SqliteStore, BaseMixin)
    assert issubclass(SqliteStore, CatalogMixin)
    assert issubclass(SqliteStore, AgriDataMixin)
    assert issubclass(SqliteStore, FieldMixin)
    assert issubclass(SqliteStore, TaskMixin)
    assert callable(utc_now_iso)


def test_allowed_tables_whitelist_matches_schema() -> None:
    """_ALLOWED_TABLES 必须与 _SCHEMA_SQL 的真实表名一致，防止旧库补列时误拒绝。"""
    import re

    schema_tables = set(
        re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-z_]+)", _SCHEMA_SQL)
    )
    assert schema_tables, "应从 _SCHEMA_SQL 中解析出表名"
    assert schema_tables <= set(BaseMixin._ALLOWED_TABLES)
    # 白名单不应包含不存在的表
    assert not (set(BaseMixin._ALLOWED_TABLES) - schema_tables)
