#!/usr/bin/env python3
"""
MPP Schema — Task/Project/Assignment/Resource dataclass.

对外契约。兼容规约：
- 字段只增不改（add-only, no rename or removal without deprecation window）
- --json 输出带 schema_version: 1
- 重命名/删除需弃用窗口 ≥ 1 版本（先加新字段 + 保留旧字段至少一次发布）
- 破坏性变更升主版本号（SCHEMA_VERSION integer bump）
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from datetime import datetime

SCHEMA_VERSION = 1


@dataclass
class Task:
    uid: int
    id: int
    name: str
    start: str = ""
    finish: str = ""
    duration: str = ""          # ISO 8601 period: PT###H##M##S (e.g. PT760H0M0S = 95 × 8h workdays)
    percent_complete: float = 0.0
    outline_level: int = 0
    summary: bool = False
    milestone: bool = False
    critical: bool = False      # Task is on critical path
    # "读优先" principle: read MPP native fields before computing
    planned_pct: Optional[float] = None
    gap_pct: Optional[float] = None
    planned_pct_source: Literal["mpp", "computed", ""] = ""
    gap_pct_source: Literal["mpp", "computed", ""] = ""
    # Baseline fields (read from MSPDI <Baseline> block)
    baseline_start: str = ""
    baseline_finish: str = ""
    baseline_duration: str = ""
    # Variance fields
    finish_variance: str = ""
    # Relationship fields
    predecessors: str = ""
    resource_names: str = ""
    notes: str = ""
    wbs: str = ""
    calendar_uid: Optional[int] = None
    # Custom numeric fields (MS Project Number1..Number20)
    number3: Optional[float] = None   # Gap% (XLSmart convention)
    number4: Optional[float] = None   # Plan% (XLSmart convention)

    def to_dict(self):
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Resource:
    uid: int
    id: int
    name: str

    def to_dict(self):
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Assignment:
    uid: int
    task_uid: int
    resource_uid: int

    def to_dict(self):
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Project:
    name: str = ""
    start: str = ""
    finish: str = ""
    tasks: list = field(default_factory=list)
    resources: list = field(default_factory=list)
    assignments: list = field(default_factory=list)

    def to_dict(self):
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "start": self.start,
            "finish": self.finish,
            "tasks": [
                t.to_dict() if hasattr(t, "to_dict") else t
                for t in self.tasks
            ],
            "resources": [
                r.to_dict() if hasattr(r, "to_dict") else asdict(r) if hasattr(r, "__dataclass_fields__") else r
                for r in self.resources
            ],
            "assignments": [
                a.to_dict() if hasattr(a, "to_dict") else asdict(a) if hasattr(a, "__dataclass_fields__") else a
                for a in self.assignments
            ],
        }
