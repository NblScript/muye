from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Project-level declarative base for future SQLAlchemy-backed services."""


class CropCategory(str, Enum):
    GRAIN = "grain"
    OIL = "oil"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    OTHER = "other"


class FieldCropStatus(str, Enum):
    PLANNED = "planned"
    PLANTED = "planted"
    GROWING = "growing"
    HARVESTED = "harvested"
    CANCELLED = "cancelled"


class CropCatalog(Base):
    """
    作物目录表。

    统一管理河南项目里的作物编码、作物基础参数和典型农时信息。
    """

    __tablename__ = "crop_catalog"

    crop_code: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="作物编码，例如 winter_wheat / summer_corn",
    )
    crop_name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="作物名称，例如冬小麦、夏玉米、花生",
    )
    category: Mapped[CropCategory | None] = mapped_column(
        SqlEnum(CropCategory, name="crop_category_enum"),
        nullable=True,
        comment="作物类型，例如粮食作物、油料作物等",
    )
    variety: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="品种或品系说明",
    )
    growth_cycle_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="典型生长周期天数",
    )
    water_demand_coefficient: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="需水量系数，用于后续天气和灌溉分析",
    )
    typical_planting_month: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="典型播种月份",
    )
    typical_harvest_month: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="典型收获月份",
    )
    source: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="数据来源标识",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="补充农业参数说明",
    )

    crop_cycles: Mapped[list["FieldCropCycle"]] = relationship(back_populates="crop")


class Field(Base):
    """
    地块表。

    地块的经纬度和围栏是天气匹配、作业规划、喷洒记录回放的核心锚点。
    """

    __tablename__ = "fields"

    field_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="地块主键 ID",
    )
    field_code: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        comment="地块业务编码",
    )
    field_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="地块名称，例如郑州示范田1号",
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="所属用户 ID",
    )
    province: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="省份",
    )
    city: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="城市",
    )
    county: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="区县",
    )
    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
        comment="地块中心点纬度，用于匹配河南天气与附近气象站",
    )
    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
        comment="地块中心点经度，用于匹配河南天气与附近气象站",
    )
    area_mu: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="地块面积，单位亩",
    )
    area_hectare: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="地块面积，单位公顷",
    )
    geofence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="地块围栏 Polygon JSON",
    )
    soil_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="土壤类型描述，例如潮土、砂壤土、黄褐土",
    )
    irrigation_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="灌溉方式描述",
    )
    source: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="数据来源标识",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="补充说明",
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )

    crop_cycles: Mapped[list["FieldCropCycle"]] = relationship(back_populates="field")


class FieldCropCycle(Base):
    """
    地块种植季记录表。

    表示“某块地在某个时间段种了什么作物”，为天气、喷洒和产量分析提供上下文。
    """

    __tablename__ = "field_crop_cycles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="种植季记录主键 ID",
    )
    field_id: Mapped[str] = mapped_column(
        ForeignKey("fields.field_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="外键，关联地块表",
    )
    crop_code: Mapped[str] = mapped_column(
        ForeignKey("crop_catalog.crop_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="外键，关联作物目录表",
    )
    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="生产季所属年份",
    )
    season: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="季节标识，例如 summer / winter",
    )
    planting_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="种植开始日期",
    )
    harvest_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="预计或实际收获日期",
    )
    area_mu: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="该季实际种植面积，单位亩",
    )
    expected_yield_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="预估产量，单位公斤",
    )
    actual_yield_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="实际产量，单位公斤",
    )
    status: Mapped[FieldCropStatus | None] = mapped_column(
        SqlEnum(FieldCropStatus, name="field_crop_status_enum"),
        nullable=True,
        comment="当前状态：planned/planted/growing/harvested/cancelled",
    )
    source: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="数据来源标识",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="补充说明",
    )

    field: Mapped[Field] = relationship(back_populates="crop_cycles")
    crop: Mapped[CropCatalog] = relationship(back_populates="crop_cycles")
