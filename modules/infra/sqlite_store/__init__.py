from modules.infra.sqlite_store._private import utc_now_iso
from modules.infra.sqlite_store.agri_data import AgriDataMixin
from modules.infra.sqlite_store.base import BaseMixin
from modules.infra.sqlite_store.catalog import CatalogMixin
from modules.infra.sqlite_store.evaluation import EvaluationMixin
from modules.infra.sqlite_store.field import FieldMixin
from modules.infra.sqlite_store.heatmap import HeatmapMixin
from modules.infra.sqlite_store.mission import MissionMixin
from modules.infra.sqlite_store.task import TaskMixin


class SqliteStore(
    MissionMixin,
    EvaluationMixin,
    HeatmapMixin,
    CatalogMixin,
    AgriDataMixin,
    FieldMixin,
    TaskMixin,
    BaseMixin,
):
    pass


__all__ = ["SqliteStore", "utc_now_iso"]
