from modules.infra.sqlite_store import SqliteStore, utc_now_iso
from modules.infra.sqlite_store.agri_data import AgriDataMixin
from modules.infra.sqlite_store.base import BaseMixin
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
