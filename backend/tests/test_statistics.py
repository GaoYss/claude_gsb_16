"""统计看板接口测试。"""

from datetime import date, timedelta


def test_overview_reflects_seeded_data(api, seeded):
    data = api.data(api.get("/api/v1/statistics/overview"))
    assert data["green_space"]["total"] == seeded["green_space"]
    assert data["green_space"]["total_area"] > 0
    assert data["green_space"]["by_status"]["archived"] == 1

    assert data["task"]["total"] == seeded["maintenance_task"]
    assert data["task"]["by_status"]["cancelled"] == 1
    assert 0 <= data["task"]["completion_rate"] <= 100

    assert data["record"]["total"] == seeded["maintenance_record"]
    assert data["record"]["total_work_hours"] > 0
    assert data["replacement"]["total"] == seeded["plant_replacement"]
    assert data["replacement"]["total_amount"] > 0


def test_overdue_and_due_soon_reminders(api, make_space, make_task):
    space = make_space()
    make_task(space=space, plan_date=date.today() - timedelta(days=3), status="pending")
    make_task(space=space, plan_date=date.today() + timedelta(days=2), status="pending")
    make_task(space=space, plan_date=date.today() - timedelta(days=3), status="completed")

    overview = api.data(api.get("/api/v1/statistics/overview"))
    assert overview["task"]["overdue_count"] == 1
    assert overview["task"]["due_soon_count"] == 1

    reminders = api.data(api.get("/api/v1/statistics/reminders"))
    assert len(reminders["overdue"]) == 1
    assert reminders["overdue"][0]["is_overdue"] is True
    assert len(reminders["upcoming"]) == 1


def test_distributions_cover_all_dimensions(api, make_task, make_replacement, make_record):
    task = make_task()
    record = make_record(task=task)
    make_replacement(record=record, plant_category="shrub", reason="aging", quantity=30, unit_price=10)

    data = api.data(api.get("/api/v1/statistics/distributions"))
    assert {item["value"] for item in data["green_space_by_type"]} == {"park"}
    assert {item["value"] for item in data["green_space_by_grade"]} == {"level2"}
    assert data["green_space_by_district"][0]["value"] == "西湖区"
    assert {item["value"] for item in data["task_by_type"]} == {"prune"}
    assert data["replacement_by_category"][0]["amount"] == 300.0
    assert data["replacement_by_reason"][0]["quantity"] == 30.0


def test_trends_return_requested_month_window(api, seeded):
    data = api.data(api.get("/api/v1/statistics/trends", months=6))
    items = data["items"]
    assert len(items) == 6
    assert items[-1]["month"] == f"{date.today():%Y-%m}"
    assert sum(item["record_count"] for item in items) == seeded["maintenance_record"]
    for item in items:
        assert set(item) == {
            "month", "record_count", "work_hours",
            "replacement_count", "replacement_quantity", "replacement_amount",
        }


def test_ranking_orders_by_record_count(api, make_space, make_record):
    busy = make_space(name="高频养护绿地")
    quiet = make_space(name="低频养护绿地")
    make_record(space=busy)
    make_record(space=busy, record_date=date(2026, 4, 2))
    make_record(space=quiet)

    items = api.data(api.get("/api/v1/statistics/ranking"))["items"]
    assert items[0]["name"] == "高频养护绿地"
    assert items[0]["record_count"] == 2
    assert items[0]["green_space_id"] == busy.id


def test_dashboard_returns_all_sections(api, seeded):
    data = api.data(api.get("/api/v1/statistics/dashboard"))
    assert set(data) == {
        "overview", "distributions", "trends", "ranking",
        "overdue_tasks", "upcoming_tasks", "recent_activity",
    }
    assert len(data["trends"]) == 6
    assert data["recent_activity"]["records"]
    assert data["recent_activity"]["replacements"]


def test_dashboard_accepts_green_space_scope(api, make_space, make_task, make_record, make_replacement):
    """看板携带绿地台账组合条件时，各板块只统计范围内的绿地。"""

    target = make_space(name="目标绿地", district="滨江区", green_type="road", area_sqm=800)
    other = make_space(name="范围外绿地", district="西湖区", green_type="park", area_sqm=9000)
    make_task(space=target, plan_date=date.today() - timedelta(days=2), status="pending")
    make_record(space=target, record_date=date.today() - timedelta(days=1))
    make_replacement(space=target, quantity=12, unit_price=10,
                     replace_date=date.today() - timedelta(days=1))
    make_task(space=other, plan_date=date.today() - timedelta(days=2), status="pending")
    make_record(space=other, record_date=date.today() - timedelta(days=1))

    data = api.data(api.get(
        "/api/v1/statistics/dashboard",
        district="滨江区", green_type="road", area_min=500, area_max=1000,
    ))

    assert data["overview"]["green_space"]["total"] == 1
    assert data["overview"]["green_space"]["total_area"] == 800.0
    assert data["overview"]["task"]["total"] == 1
    assert data["overview"]["task"]["overdue_count"] == 1
    assert data["overview"]["record"]["total"] == 1
    assert data["overview"]["replacement"]["total"] == 1
    assert {item["value"] for item in data["distributions"]["green_space_by_type"]} == {"road"}
    assert data["ranking"][0]["name"] == "目标绿地"
    assert len(data["overdue_tasks"]) == 1
    assert data["overdue_tasks"][0]["green_space_id"] == target.id
    assert len(data["recent_activity"]["records"]) == 1
    assert data["recent_activity"]["records"][0]["green_space_id"] == target.id
    assert len(data["recent_activity"]["replacements"]) == 1
    assert sum(item["record_count"] for item in data["trends"]) == 1

    # 不存在的范围：看板各板块为空但结构不变
    empty = api.data(api.get("/api/v1/statistics/dashboard", district="不存在的区"))
    assert empty["overview"]["green_space"]["total"] == 0
    assert empty["overview"]["task"]["total"] == 0
    assert empty["distributions"]["green_space_by_type"] == []
    assert empty["overdue_tasks"] == []
