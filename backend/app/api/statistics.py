"""统计看板接口。"""

from flask import Blueprint, request

from ..schemas import green_space_filters
from ..services import StatisticsService
from ..utils.responses import ok

bp = Blueprint("statistics", __name__)


def _months():
    try:
        months = int(request.args.get("months", 6))
    except (TypeError, ValueError):
        months = 6
    return min(max(months, 1), 24)


def _scope():
    """台账筛选条件：行政区/类型/等级/状态/面积区间，跟随看板一起收窄统计范围。"""

    return green_space_filters(request.args)


@bp.get("/statistics/dashboard")
def dashboard():
    """看板聚合接口：一次返回总览、分布、趋势、榜单与提醒。"""

    return ok(StatisticsService.dashboard(_months(), _scope()))


@bp.get("/statistics/overview")
def overview():
    return ok(StatisticsService.overview(_scope()))


@bp.get("/statistics/distributions")
def distributions():
    return ok(StatisticsService.distributions(_scope()))


@bp.get("/statistics/trends")
def trends():
    return ok({"items": StatisticsService.trends(_months(), _scope())})


@bp.get("/statistics/ranking")
def ranking():
    try:
        limit = int(request.args.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    return ok({"items": StatisticsService.green_space_ranking(min(max(limit, 1), 20), _scope())})


@bp.get("/statistics/reminders")
def reminders():
    """逾期与即将到期的养护任务提醒。"""

    scope = _scope()
    return ok({
        "overdue": StatisticsService.overdue_tasks(space_filters=scope),
        "upcoming": StatisticsService.upcoming_tasks(space_filters=scope),
    })
