"""统计看板：全部使用聚合查询，不把明细数据搬到前端计算。

space_filters：来自绿地台账的组合检索条件（行政区、类型、养护等级、状态、面积区间）。
传入后，任务/记录/更换等跨模块统计通过 join 绿地台账下推，使看板与台账列表同口径。
"""

from datetime import timedelta

from sqlalchemy import func, or_

from ..constants import ENUM_GROUPS
from ..extensions import db
from ..models import GreenSpace, MaintenanceRecord, MaintenanceTask, PlantReplacement
from ..models.maintenance_task import OPEN_STATUSES
from ..utils.dates import today
from ..utils.numbers import to_float


class StatisticsService:
    """看板与各类分布统计。"""

    # ------------------------------------------------------------ 范围条件
    @staticmethod
    def _space_clauses(space_filters):
        """把台账筛选条件翻译成 GreenSpace 列上的条件列表。"""

        filters = space_filters or {}
        clauses = []
        if filters.get("green_type"):
            clauses.append(GreenSpace.green_type == filters["green_type"])
        if filters.get("maintenance_grade"):
            clauses.append(GreenSpace.maintenance_grade == filters["maintenance_grade"])
        if filters.get("status"):
            clauses.append(GreenSpace.status == filters["status"])
        if filters.get("district"):
            clauses.append(GreenSpace.district == filters["district"])
        if filters.get("area_min") is not None:
            clauses.append(GreenSpace.area_sqm >= filters["area_min"])
        if filters.get("area_max") is not None:
            clauses.append(GreenSpace.area_sqm <= filters["area_max"])
        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            clauses.append(
                or_(
                    GreenSpace.name.like(like),
                    GreenSpace.code.like(like),
                    GreenSpace.district.like(like),
                    GreenSpace.address.like(like),
                    GreenSpace.manager.like(like),
                )
            )
        return clauses

    @staticmethod
    def _scope_green_space_query(query, clauses):
        return query.filter(*clauses) if clauses else query

    @staticmethod
    def _scope_related_query(query, model, clauses):
        """跨模块统计：join 绿地台账后追加范围条件。"""

        if not clauses:
            return query
        return query.join(GreenSpace, model.green_space_id == GreenSpace.id).filter(*clauses)

    # ------------------------------------------------------------ 工具
    @staticmethod
    def _month_starts(months):
        cursor = today().replace(day=1)
        starts = []
        for _ in range(max(months, 1)):
            starts.append(cursor)
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        return list(reversed(starts))

    # ------------------------------------------------------------ 总览
    @staticmethod
    def overview(space_filters=None):
        current = today()
        month_start = current.replace(day=1)
        year_start = current.replace(month=1, day=1)
        clauses = StatisticsService._space_clauses(space_filters)

        space_total, space_area = StatisticsService._scope_green_space_query(
            db.session.query(
                func.count(GreenSpace.id), func.coalesce(func.sum(GreenSpace.area_sqm), 0)
            ),
            clauses,
        ).one()
        space_rows = StatisticsService._scope_green_space_query(
            db.session.query(GreenSpace.status, func.count(GreenSpace.id)),
            clauses,
        ).group_by(GreenSpace.status).all()
        space_status = {code: 0 for code in ENUM_GROUPS["green_space_status"].values}
        for status, count in space_rows:
            space_status[status] = count

        task_rows = StatisticsService._scope_related_query(
            db.session.query(MaintenanceTask.status, func.count(MaintenanceTask.id)),
            MaintenanceTask,
            clauses,
        ).group_by(MaintenanceTask.status).all()
        task_status = {code: 0 for code in ENUM_GROUPS["task_status"].values}
        for status, count in task_rows:
            task_status[status] = count
        task_total = sum(task_status.values())

        overdue = StatisticsService._scope_related_query(
            db.session.query(func.count(MaintenanceTask.id)),
            MaintenanceTask,
            clauses,
        ).filter(
            MaintenanceTask.status.in_(OPEN_STATUSES), MaintenanceTask.plan_date < current
        ).scalar() or 0
        due_soon = StatisticsService._scope_related_query(
            db.session.query(func.count(MaintenanceTask.id)),
            MaintenanceTask,
            clauses,
        ).filter(
            MaintenanceTask.status.in_(OPEN_STATUSES),
            MaintenanceTask.plan_date >= current,
            MaintenanceTask.plan_date <= current + timedelta(days=7),
        ).scalar() or 0

        record_total, hours_total = StatisticsService._scope_related_query(
            db.session.query(
                func.count(MaintenanceRecord.id),
                func.coalesce(func.sum(MaintenanceRecord.work_hours), 0),
            ),
            MaintenanceRecord,
            clauses,
        ).one()
        month_records, month_hours = StatisticsService._scope_related_query(
            db.session.query(
                func.count(MaintenanceRecord.id),
                func.coalesce(func.sum(MaintenanceRecord.work_hours), 0),
            ),
            MaintenanceRecord,
            clauses,
        ).filter(MaintenanceRecord.record_date >= month_start).one()

        replacement_total, quantity_total, amount_total = StatisticsService._scope_related_query(
            db.session.query(
                func.count(PlantReplacement.id),
                func.coalesce(func.sum(PlantReplacement.quantity), 0),
                func.coalesce(func.sum(PlantReplacement.amount), 0),
            ),
            PlantReplacement,
            clauses,
        ).one()
        month_count, month_quantity, month_amount = StatisticsService._scope_related_query(
            db.session.query(
                func.count(PlantReplacement.id),
                func.coalesce(func.sum(PlantReplacement.quantity), 0),
                func.coalesce(func.sum(PlantReplacement.amount), 0),
            ),
            PlantReplacement,
            clauses,
        ).filter(PlantReplacement.replace_date >= month_start).one()
        _, year_quantity, year_amount = StatisticsService._scope_related_query(
            db.session.query(
                func.count(PlantReplacement.id),
                func.coalesce(func.sum(PlantReplacement.quantity), 0),
                func.coalesce(func.sum(PlantReplacement.amount), 0),
            ),
            PlantReplacement,
            clauses,
        ).filter(PlantReplacement.replace_date >= year_start).one()

        completed = task_status.get("completed", 0)
        return {
            "generated_at": f"{current:%Y-%m-%d}",
            "green_space": {
                "total": space_total or 0,
                "total_area": to_float(space_area) or 0,
                "by_status": space_status,
            },
            "task": {
                "total": task_total,
                "by_status": task_status,
                "open_count": task_status.get("pending", 0) + task_status.get("in_progress", 0),
                "overdue_count": overdue,
                "due_soon_count": due_soon,
                "completion_rate": round(completed / task_total * 100, 1) if task_total else 0.0,
            },
            "record": {
                "total": record_total or 0,
                "total_work_hours": to_float(hours_total) or 0,
                "month_count": month_records or 0,
                "month_work_hours": to_float(month_hours) or 0,
            },
            "replacement": {
                "total": replacement_total or 0,
                "total_quantity": to_float(quantity_total) or 0,
                "total_amount": to_float(amount_total) or 0,
                "month_count": month_count or 0,
                "month_quantity": to_float(month_quantity) or 0,
                "month_amount": to_float(month_amount) or 0,
                "year_quantity": to_float(year_quantity) or 0,
                "year_amount": to_float(year_amount) or 0,
            },
        }

    # ------------------------------------------------------------ 分布
    @staticmethod
    def distributions(space_filters=None):
        clauses = StatisticsService._space_clauses(space_filters)

        type_rows = StatisticsService._scope_green_space_query(
            db.session.query(
                GreenSpace.green_type,
                func.count(GreenSpace.id),
                func.coalesce(func.sum(GreenSpace.area_sqm), 0),
            ),
            clauses,
        ).group_by(GreenSpace.green_type).all()
        grade_rows = StatisticsService._scope_green_space_query(
            db.session.query(
                GreenSpace.maintenance_grade,
                func.count(GreenSpace.id),
                func.coalesce(func.sum(GreenSpace.area_sqm), 0),
            ),
            clauses,
        ).group_by(GreenSpace.maintenance_grade).all()
        district_rows = StatisticsService._scope_green_space_query(
            db.session.query(
                GreenSpace.district,
                func.count(GreenSpace.id),
                func.coalesce(func.sum(GreenSpace.area_sqm), 0),
            ),
            clauses,
        ).group_by(GreenSpace.district).order_by(func.count(GreenSpace.id).desc()).limit(10).all()
        task_type_rows = StatisticsService._scope_related_query(
            db.session.query(MaintenanceTask.task_type, func.count(MaintenanceTask.id)),
            MaintenanceTask,
            clauses,
        ).group_by(MaintenanceTask.task_type).all()
        priority_rows = StatisticsService._scope_related_query(
            db.session.query(MaintenanceTask.priority, func.count(MaintenanceTask.id)),
            MaintenanceTask,
            clauses,
        ).group_by(MaintenanceTask.priority).all()
        category_rows = StatisticsService._scope_related_query(
            db.session.query(
                PlantReplacement.plant_category,
                func.count(PlantReplacement.id),
                func.coalesce(func.sum(PlantReplacement.quantity), 0),
                func.coalesce(func.sum(PlantReplacement.amount), 0),
            ),
            PlantReplacement,
            clauses,
        ).group_by(PlantReplacement.plant_category).all()
        reason_rows = StatisticsService._scope_related_query(
            db.session.query(
                PlantReplacement.reason,
                func.count(PlantReplacement.id),
                func.coalesce(func.sum(PlantReplacement.quantity), 0),
            ),
            PlantReplacement,
            clauses,
        ).group_by(PlantReplacement.reason).all()

        def _with_area(group_key, rows):
            return [
                {
                    "value": value,
                    "label": ENUM_GROUPS[group_key].label(value),
                    "count": count,
                    "area_sqm": to_float(area) or 0,
                }
                for value, count, area in rows
            ]

        def _simple(group_key, rows):
            return [
                {"value": value, "label": ENUM_GROUPS[group_key].label(value), "count": count}
                for value, count in rows
            ]

        return {
            "green_space_by_type": _with_area("green_space_type", type_rows),
            "green_space_by_grade": _with_area("maintenance_grade", grade_rows),
            "green_space_by_district": [
                {
                    "value": district,
                    "label": district,
                    "count": count,
                    "area_sqm": to_float(area) or 0,
                }
                for district, count, area in district_rows
            ],
            "task_by_type": _simple("task_type", task_type_rows),
            "task_by_priority": _simple("task_priority", priority_rows),
            "replacement_by_category": [
                {
                    "value": value,
                    "label": ENUM_GROUPS["plant_category"].label(value),
                    "count": count,
                    "quantity": to_float(quantity) or 0,
                    "amount": to_float(amount) or 0,
                }
                for value, count, quantity, amount in category_rows
            ],
            "replacement_by_reason": [
                {
                    "value": value,
                    "label": ENUM_GROUPS["replacement_reason"].label(value),
                    "count": count,
                    "quantity": to_float(quantity) or 0,
                }
                for value, count, quantity in reason_rows
            ],
        }

    # ------------------------------------------------------------ 趋势
    @staticmethod
    def trends(months=6, space_filters=None):
        """近 N 个月的养护记录与绿植更换趋势（按自然月聚合）。"""

        starts = StatisticsService._month_starts(months)
        buckets = {}
        for start in starts:
            buckets[f"{start:%Y-%m}"] = {
                "month": f"{start:%Y-%m}",
                "record_count": 0,
                "work_hours": 0.0,
                "replacement_count": 0,
                "replacement_quantity": 0.0,
                "replacement_amount": 0.0,
            }

        clauses = StatisticsService._space_clauses(space_filters)
        start = starts[0]
        record_rows = StatisticsService._scope_related_query(
            db.session.query(MaintenanceRecord.record_date, MaintenanceRecord.work_hours),
            MaintenanceRecord,
            clauses,
        ).filter(MaintenanceRecord.record_date >= start).all()
        for record_date, work_hours in record_rows:
            bucket = buckets.get(f"{record_date:%Y-%m}")
            if bucket is None:
                continue
            bucket["record_count"] += 1
            bucket["work_hours"] = round(bucket["work_hours"] + float(work_hours or 0), 2)

        replacement_rows = StatisticsService._scope_related_query(
            db.session.query(
                PlantReplacement.replace_date,
                PlantReplacement.quantity,
                PlantReplacement.amount,
            ),
            PlantReplacement,
            clauses,
        ).filter(PlantReplacement.replace_date >= start).all()
        for replace_date, quantity, amount in replacement_rows:
            bucket = buckets.get(f"{replace_date:%Y-%m}")
            if bucket is None:
                continue
            bucket["replacement_count"] += 1
            bucket["replacement_quantity"] = round(
                bucket["replacement_quantity"] + float(quantity or 0), 2
            )
            bucket["replacement_amount"] = round(
                bucket["replacement_amount"] + float(amount or 0), 2
            )

        return [buckets[f"{start:%Y-%m}"] for start in starts]

    # ------------------------------------------------------------ 榜单与提醒
    @staticmethod
    def green_space_ranking(limit=5, space_filters=None):
        replacement_quantity = (
            db.select(func.coalesce(func.sum(PlantReplacement.quantity), 0))
            .where(PlantReplacement.green_space_id == GreenSpace.id)
            .correlate(GreenSpace)
            .scalar_subquery()
        )
        clauses = StatisticsService._space_clauses(space_filters)
        query = (
            db.session.query(
                GreenSpace.id,
                GreenSpace.code,
                GreenSpace.name,
                GreenSpace.district,
                GreenSpace.area_sqm,
                func.count(MaintenanceRecord.id),
                func.coalesce(func.sum(MaintenanceRecord.work_hours), 0),
                replacement_quantity,
            )
            .join(MaintenanceRecord, MaintenanceRecord.green_space_id == GreenSpace.id)
        )
        if clauses:
            query = query.filter(*clauses)
        rows = (
            query
            .group_by(GreenSpace.id, GreenSpace.code, GreenSpace.name, GreenSpace.district,
                      GreenSpace.area_sqm)
            .order_by(func.count(MaintenanceRecord.id).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "green_space_id": space_id,
                "code": code,
                "name": name,
                "district": district,
                "area_sqm": to_float(area) or 0,
                "record_count": record_count,
                "total_work_hours": to_float(hours) or 0,
                "replacement_quantity": to_float(quantity) or 0,
            }
            for space_id, code, name, district, area, record_count, hours, quantity in rows
        ]

    @staticmethod
    def overdue_tasks(limit=10, space_filters=None):
        clauses = StatisticsService._space_clauses(space_filters)
        tasks = StatisticsService._scope_related_query(
            db.session.query(MaintenanceTask),
            MaintenanceTask,
            clauses,
        ).filter(
            MaintenanceTask.status.in_(OPEN_STATUSES),
            MaintenanceTask.plan_date < today(),
        ).order_by(MaintenanceTask.plan_date.asc()).limit(limit).all()
        return [task.to_dict() for task in tasks]

    @staticmethod
    def upcoming_tasks(limit=10, space_filters=None):
        clauses = StatisticsService._space_clauses(space_filters)
        tasks = StatisticsService._scope_related_query(
            db.session.query(MaintenanceTask),
            MaintenanceTask,
            clauses,
        ).filter(
            MaintenanceTask.status.in_(OPEN_STATUSES),
            MaintenanceTask.plan_date >= today(),
        ).order_by(MaintenanceTask.plan_date.asc()).limit(limit).all()
        return [task.to_dict() for task in tasks]

    @staticmethod
    def recent_activity(limit=6, space_filters=None):
        clauses = StatisticsService._space_clauses(space_filters)
        records = StatisticsService._scope_related_query(
            db.session.query(MaintenanceRecord),
            MaintenanceRecord,
            clauses,
        ).order_by(
            MaintenanceRecord.record_date.desc(), MaintenanceRecord.id.desc()
        ).limit(limit).all()
        replacements = StatisticsService._scope_related_query(
            db.session.query(PlantReplacement),
            PlantReplacement,
            clauses,
        ).order_by(
            PlantReplacement.replace_date.desc(), PlantReplacement.id.desc()
        ).limit(limit).all()
        return {
            "records": [item.to_dict() for item in records],
            "replacements": [item.to_dict() for item in replacements],
        }

    # ------------------------------------------------------------ 汇总入口
    @staticmethod
    def dashboard(months=6, space_filters=None):
        """看板一次性取数，减少前端并发请求。传入台账条件时各板块同口径收敛。"""

        return {
            "overview": StatisticsService.overview(space_filters),
            "distributions": StatisticsService.distributions(space_filters),
            "trends": StatisticsService.trends(months, space_filters),
            "ranking": StatisticsService.green_space_ranking(space_filters=space_filters),
            "overdue_tasks": StatisticsService.overdue_tasks(space_filters=space_filters),
            "upcoming_tasks": StatisticsService.upcoming_tasks(space_filters=space_filters),
            "recent_activity": StatisticsService.recent_activity(space_filters=space_filters),
        }
