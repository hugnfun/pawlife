"""
Celery 异步任务定义。

核心异步任务：
1. generate_daily_report — 每日健康晨报生成
2. send_reminder — 定时提醒推送
3. check_and_send_reminders — Beat 定时检查待发送提醒
4. process_nutrition — 营养分析计算
"""

import json
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional

from services.celery_app import celery_app

logger = logging.getLogger(__name__)


# ========== 数据库同步查询辅助 ==========

def _get_sync_engine():
    """创建同步数据库引擎（Celery worker 中使用）。"""
    from sqlalchemy import create_engine
    from core.config import settings
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(sync_url, pool_size=5, max_overflow=10)


def _query_pet_health_data(engine, pet_id: str, days: int = 30) -> dict:
    """查询宠物健康数据用于报告生成。"""
    from sqlalchemy import text
    cutoff = datetime.utcnow() - timedelta(days=days)

    with engine.connect() as conn:
        # 宠物基本信息
        pet_row = conn.execute(
            text("SELECT name, species, current_weight, ideal_weight FROM pets WHERE id = :pid"),
            {"pid": pet_id}
        ).fetchone()

        if not pet_row:
            return {"error": "pet_not_found"}

        # 饮食记录统计
        meal_stats = conn.execute(
            text("""
                SELECT COUNT(*) as total_meals,
                       COUNT(DISTINCT DATE(meal_time)) as feeding_days,
                       SUM(amount) as total_amount
                FROM meal_logs
                WHERE pet_id = :pid AND meal_time >= :cutoff
            """),
            {"pid": pet_id, "cutoff": cutoff}
        ).fetchone()

        # 体重趋势
        weight_rows = conn.execute(
            text("""
                SELECT weight, measurement_time
                FROM weight_logs
                WHERE pet_id = :pid AND measurement_time >= :cutoff
                ORDER BY measurement_time
            """),
            {"pid": pet_id, "cutoff": cutoff}
        ).fetchall()

        # 活动记录统计
        activity_stats = conn.execute(
            text("""
                SELECT COUNT(*) as total_activities,
                       SUM(duration_minutes) as total_minutes,
                       SUM(calories_estimated) as total_calories
                FROM activity_logs
                WHERE pet_id = :pid AND activity_time >= :cutoff
            """),
            {"pid": pet_id, "cutoff": cutoff}
        ).fetchone()

        # 最近 7 天饮食明细
        recent_meals = conn.execute(
            text("""
                SELECT food_name, food_type, amount, meal_time
                FROM meal_logs
                WHERE pet_id = :pid AND meal_time >= :week_ago
                ORDER BY meal_time DESC
                LIMIT 20
            """),
            {"pid": pet_id, "week_ago": datetime.utcnow() - timedelta(days=7)}
        ).fetchall()

        weight_trend = [
            {"weight": float(w.weight), "date": w.measurement_time.isoformat()}
            for w in weight_rows
        ]

        weight_change = 0.0
        if len(weight_rows) >= 2:
            weight_change = float(weight_rows[-1].weight - weight_rows[0].weight)

        return {
            "pet_name": pet_row.name,
            "species": pet_row.species,
            "current_weight": float(pet_row.current_weight) if pet_row.current_weight else None,
            "ideal_weight": float(pet_row.ideal_weight) if pet_row.ideal_weight else None,
            "period_days": days,
            "total_meals": meal_stats.total_meals or 0,
            "feeding_days": meal_stats.feeding_days or 0,
            "total_food_amount": float(meal_stats.total_amount) if meal_stats.total_amount else 0,
            "weight_trend": weight_trend,
            "weight_change": weight_change,
            "total_activities": activity_stats.total_activities or 0,
            "total_activity_minutes": activity_stats.total_minutes or 0,
            "total_activity_calories": float(activity_stats.total_calories) if activity_stats.total_calories else 0,
            "recent_meals": [
                {
                    "food_name": m.food_name,
                    "food_type": m.food_type,
                    "amount": float(m.amount),
                    "meal_time": m.meal_time.isoformat(),
                }
                for m in recent_meals
            ],
        }


def _query_pending_reminders(engine) -> list:
    """查询所有到期未发送的提醒。"""
    from sqlalchemy import text
    now = datetime.utcnow()

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT r.id, r.pet_id, r.user_id, r.reminder_type, r.title, r.description
                FROM reminders r
                WHERE r.is_active = true
                  AND r.status = 'pending'
                  AND r.remind_at <= :now
                ORDER BY r.remind_at
            """),
            {"now": now}
        ).fetchall()

        return [
            {
                "reminder_id": str(r.id),
                "pet_id": str(r.pet_id),
                "user_id": str(r.user_id),
                "reminder_type": r.reminder_type,
                "title": r.title,
                "description": r.description,
            }
            for r in rows
        ]


def _mark_reminder_sent(engine, reminder_id: str):
    """将提醒标记为已发送。"""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE reminders
                SET status = 'sent', last_reminded_at = :now
                WHERE id = :rid
            """),
            {"rid": reminder_id, "now": datetime.utcnow()}
        )
        conn.commit()


# ========== 微信推送 ==========

def _send_wechat_subscribe_message(user_id: str, template_data: dict) -> bool:
    """发送微信订阅消息。

    使用微信小程序订阅消息 API 推送提醒。
    生产环境需先获取 access_token。

    Args:
        user_id: 用户 ID（用于查 openid）
        template_data: 模板消息数据

    Returns:
        是否发送成功
    """
    try:
        import httpx
        from core.config import settings

        if not settings.wechat_app_id or not settings.wechat_app_secret:
            logger.warning("微信配置缺失，跳过推送")
            return False

        # 获取用户 openid
        engine = _get_sync_engine()
        with engine.connect() as conn:
            from sqlalchemy import text
            row = conn.execute(
                text("SELECT wechat_openid FROM users WHERE id = :uid"),
                {"uid": user_id}
            ).fetchone()

        if not row:
            logger.error(f"用户不存在: {user_id}")
            return False

        openid = row.wechat_openid

        # 获取 access_token
        token_url = "https://api.weixin.qq.com/cgi-bin/token"
        token_resp = httpx.get(token_url, params={
            "grant_type": "client_credential",
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
        }, timeout=10)
        token_data = token_resp.json()

        if "access_token" not in token_data:
            logger.error(f"获取 access_token 失败: {token_data}")
            return False

        access_token = token_data["access_token"]

        # 发送订阅消息
        send_url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}"
        payload = {
            "touser": openid,
            "template_id": template_data.get("template_id", ""),
            "page": template_data.get("page", "pages/chat/index"),
            "data": template_data.get("data", {}),
        }

        resp = httpx.post(send_url, json=payload, timeout=10)
        result = resp.json()

        if result.get("errcode", 0) != 0:
            logger.warning(f"微信推送返回错误: {result}")
            return False

        logger.info(f"微信推送成功: user_id={user_id}")
        return True

    except Exception as e:
        logger.error(f"微信推送异常: {e}")
        return False


# ========== Celery 任务 ==========

@celery_app.task(
    name="services.tasks.generate_daily_report",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_daily_report(self, pet_id: str, user_id: str):
    """生成每日健康晨报。

    聚合过去 24 小时的饮食、体重、活动数据，
    通过微信订阅消息推送摘要给用户。

    Args:
        pet_id: 宠物 ID
        user_id: 用户 ID
    """
    logger.info(f"生成每日晨报: pet_id={pet_id}, user_id={user_id}")

    try:
        engine = _get_sync_engine()
        health_data = _query_pet_health_data(engine, pet_id, days=1)

        if "error" in health_data:
            logger.error(f"查询健康数据失败: {health_data['error']}")
            return {"success": False, "error": health_data["error"]}

        # 生成晨报摘要
        pet_name = health_data["pet_name"]
        meals_today = health_data["total_meals"]
        weight = health_data["current_weight"]
        activities = health_data["total_activities"]
        activity_min = health_data["total_activity_minutes"]

        summary_parts = [f"📋 {pet_name} 昨日健康总结\n"]

        if meals_today > 0:
            summary_parts.append(f"🍽️ 饮食: {meals_today} 顿")
        else:
            summary_parts.append("🍽️ 饮食: 昨日未记录喂食")

        if weight:
            summary_parts.append(f"⚖️ 体重: {weight}kg")

        if activities > 0:
            summary_parts.append(f"🏃 运动: {activity_min}分钟")
        else:
            summary_parts.append("🏃 运动: 昨日未记录活动")

        # 推送微信订阅消息
        _send_wechat_subscribe_message(user_id, {
            "template_id": "daily_report",
            "data": {
                "thing1": {"value": pet_name},
                "thing2": {"value": f"饮食{meals_today}顿, 运动{activity_min}分钟"},
                "time3": {"value": datetime.utcnow().strftime("%Y-%m-%d %H:%M")},
            },
        })

        report_text = "\n".join(summary_parts)
        logger.info(f"晨报生成完成: pet_id={pet_id}")

        return {"success": True, "pet_id": pet_id, "report": report_text}

    except Exception as exc:
        logger.error(f"晨报生成失败: pet_id={pet_id}, error={exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    name="services.tasks.send_reminder",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_reminder(self, reminder_id: str, user_id: str, pet_id: str,
                  reminder_type: str, title: str, description: str = ""):
    """发送提醒通知。

    通过微信订阅消息推送到用户微信。

    Args:
        reminder_id: 提醒 ID
        user_id: 用户 ID
        pet_id: 宠物 ID
        reminder_type: 提醒类型
        title: 提醒标题
        description: 提醒描述
    """
    logger.info(f"发送提醒: reminder_id={reminder_id}, type={reminder_type}, title={title}")

    try:
        # 获取宠物名
        engine = _get_sync_engine()
        pet_name = ""
        with engine.connect() as conn:
            from sqlalchemy import text
            row = conn.execute(
                text("SELECT name FROM pets WHERE id = :pid"),
                {"pid": pet_id}
            ).fetchone()
            if row:
                pet_name = row.name

        reminder_labels = {
            "feeding": "喂食提醒",
            "medication": "用药提醒",
            "deworming": "驱虫提醒",
            "vaccine": "疫苗提醒",
            "weighing": "称重提醒",
            "bath": "洗澡提醒",
            "nail_trim": "剪指甲提醒",
        }

        label = reminder_labels.get(reminder_type, "提醒")
        message = f"🐾 {pet_name} - {label}: {title}"
        if description:
            message += f"\n{description}"

        # 推送微信订阅消息
        push_success = _send_wechat_subscribe_message(user_id, {
            "template_id": "reminder",
            "page": "pages/chat/index",
            "data": {
                "thing1": {"value": pet_name},
                "thing2": {"value": f"{label}: {title}"},
                "time3": {"value": datetime.utcnow().strftime("%Y-%m-%d %H:%M")},
            },
        })

        # 标记提醒已发送
        _mark_reminder_sent(engine, reminder_id)

        logger.info(f"提醒发送完成: reminder_id={reminder_id}, push_success={push_success}")
        return {"success": True, "reminder_id": reminder_id, "push_success": push_success}

    except Exception as exc:
        logger.error(f"提醒发送失败: reminder_id={reminder_id}, error={exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="services.tasks.check_and_send_reminders")
def check_and_send_reminders():
    """Beat 定时任务：检查并发送到期提醒。

    每分钟执行一次，查询所有到期的 pending 提醒并发送。
    """
    logger.info("检查待发送提醒...")

    try:
        engine = _get_sync_engine()
        pending = _query_pending_reminders(engine)

        if not pending:
            return {"success": True, "sent_count": 0}

        sent_count = 0
        for r in pending:
            try:
                send_reminder.delay(
                    reminder_id=r["reminder_id"],
                    user_id=r["user_id"],
                    pet_id=r["pet_id"],
                    reminder_type=r["reminder_type"],
                    title=r["title"],
                    description=r.get("description", ""),
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"派发提醒任务失败: {r['reminder_id']}, error={e}")

        logger.info(f"提醒检查完成: 待发送={len(pending)}, 已派发={sent_count}")
        return {"success": True, "sent_count": sent_count}

    except Exception as e:
        logger.error(f"提醒检查失败: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(name="services.tasks.generate_morning_reports")
def generate_morning_reports():
    """Beat 定时任务：为所有开启晨报的用户生成每日晨报。

    每天早上 7:00 执行。
    """
    logger.info("生成每日晨报...")

    try:
        import json as _json
        from services.redis import redis_service

        engine = _get_sync_engine()

        # 查询所有活跃宠物
        with engine.connect() as conn:
            from sqlalchemy import text
            rows = conn.execute(
                text("""
                    SELECT p.id as pet_id, p.owner_id as user_id
                    FROM pets p
                    WHERE p.is_active = true
                """)
            ).fetchall()

        sent_count = 0
        for row in rows:
            pet_id = str(row.pet_id)
            user_id = str(row.owner_id)

            # 检查用户是否开启了晨报推送
            try:
                settings_data = await_sync(redis_service.get, f"push_settings:{user_id}")
                if settings_data:
                    if isinstance(settings_data, str):
                        settings_data = _json.loads(settings_data)
                    if not settings_data.get("daily_summary", False):
                        continue
            except Exception:
                pass  # 读取失败时默认发送

            try:
                generate_daily_report.delay(pet_id=pet_id, user_id=user_id)
                sent_count += 1
            except Exception as e:
                logger.error(f"派发晨报任务失败: pet_id={pet_id}, error={e}")

        logger.info(f"晨报派发完成: 共{len(rows)}只活跃宠物, 派发{sent_count}份晨报")
        return {"success": True, "sent_count": sent_count}

    except Exception as e:
        logger.error(f"晨报生成失败: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    name="services.tasks.process_nutrition",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def process_nutrition(self, pet_id: str, food_items: list):
    """异步处理营养分析。

    根据 FoodNutrition 表数据计算实际摄入，
    并对照 AAFCO 标准进行评估。

    Args:
        pet_id: 宠物 ID
        food_items: 食物列表 [{"food_name": str, "amount": float}]
    """
    logger.info(f"营养分析: pet_id={pet_id}, items={len(food_items)}")

    try:
        from sqlalchemy import text

        engine = _get_sync_engine()

        # 获取宠物体重（用于 AAFCO 计算）
        pet_weight = 5.0  # 默认 5kg
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT current_weight FROM pets WHERE id = :pid"),
                {"pid": pet_id}
            ).fetchone()
            if row and row.current_weight:
                pet_weight = float(row.current_weight)

        # 查询每种食物的营养数据
        total = {
            "calories": 0.0, "protein": 0.0, "fat": 0.0,
            "carbs": 0.0, "fiber": 0.0, "calcium": 0.0, "phosphorus": 0.0,
        }
        food_details = []

        with engine.connect() as conn:
            for item in food_items:
                food_name = item.get("food_name", "")
                amount = item.get("amount", 100)  # 默认 100g

                row = conn.execute(
                    text("""
                        SELECT calories, protein, fat, carbs, fiber, calcium, phosphorus
                        FROM food_nutritions
                        WHERE food_name = :fname
                        LIMIT 1
                    """),
                    {"fname": food_name}
                ).fetchone()

                if row:
                    factor = amount / 100.0
                    nutrients = {
                        "calories": float(row.calories or 0) * factor,
                        "protein": float(row.protein or 0) * factor,
                        "fat": float(row.fat or 0) * factor,
                        "carbs": float(row.carbs or 0) * factor,
                        "fiber": float(row.fiber or 0) * factor,
                        "calcium": float(row.calcium or 0) * factor,
                        "phosphorus": float(row.phosphorus or 0) * factor,
                    }
                    for k, v in nutrients.items():
                        total[k] += v
                    food_details.append({"food_name": food_name, "amount": amount, **nutrients})
                else:
                    food_details.append({"food_name": food_name, "amount": amount, "found": False})

        # AAFCO 评估（成年犬最低标准，按体重 kg 计算）
        aafco = {
            "protein": pet_weight * 5.0,     # g/day
            "fat": pet_weight * 1.3,          # g/day
            "calcium": pet_weight * 0.05,     # g/day
            "phosphorus": pet_weight * 0.04,  # g/day
        }

        evaluation = {}
        for nutrient, daily_need in aafco.items():
            actual = total.get(nutrient, 0)
            if daily_need > 0:
                ratio = actual / daily_need
                if ratio < 0.8:
                    status = "不足"
                elif ratio > 1.5:
                    status = "过量"
                else:
                    status = "达标"
                evaluation[nutrient] = {
                    "actual": round(actual, 2),
                    "recommended": round(daily_need, 2),
                    "ratio": round(ratio, 2),
                    "status": status,
                }

        logger.info(f"营养分析完成: pet_id={pet_id}")
        return {
            "success": True,
            "pet_id": pet_id,
            "pet_weight": pet_weight,
            "total_nutrients": {k: round(v, 2) for k, v in total.items()},
            "food_details": food_details,
            "evaluation": evaluation,
        }

    except Exception as exc:
        logger.error(f"营养分析失败: pet_id={pet_id}, error={exc}")
        raise self.retry(exc=exc)


def await_sync(coro):
    """在同步上下文中运行异步协程的辅助函数。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
