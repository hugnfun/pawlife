"""
审计日志中间件。

自动记录所有写操作（POST/PUT/DELETE）到 AuditLog 表。
"""

import logging
import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

logger = logging.getLogger(__name__)

# 需要审计的 HTTP 方法
AUDITED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件。

    拦截写操作请求，记录操作详情到 AuditLog。
    注意：实际写入在响应后异步执行。
    """

    async def dispatch(self, request: Request, call_next):
        # 跳过审计排除路径
        if not settings.audit_enabled:
            return await call_next(request)

        path = request.url.path

        # 跳过排除路径
        if any(path.startswith(excluded) for excluded in settings.audit_exclude_paths):
            return await call_next(request)

        # 只审计写操作
        if request.method not in AUDITED_METHODS:
            return await call_next(request)

        start_time = time.time()

        # 提取请求信息
        user_id = getattr(request.state, "user_id", None) or "anonymous"
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]

        # 获取请求体（仅记录非敏感字段）
        request_body = await self._get_safe_body(request)

        # 执行请求
        response = await call_next(request)
        duration = time.time() - start_time

        # 构建审计日志
        resource_type = self._extract_resource_type(path)
        resource_id = self._extract_resource_id(path)
        action = self._method_to_action(request.method)
        audit_status = "success" if response.status_code < 400 else "failure"

        # 异步写入审计日志（不阻塞响应）
        audit_data = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": {
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "request_body_keys": list(request_body.keys()) if isinstance(request_body, dict) else [],
            },
            "ip_address": client_ip,
            "user_agent": user_agent,
            "status": audit_status,
        }

        if audit_status == "failure":
            audit_data["error_message"] = f"HTTP {response.status_code}"

        # 记录日志（不阻塞响应）
        logger.info(
            f"AUDIT: user={user_id} action={action} "
            f"resource={resource_type}/{resource_id} "
            f"status={audit_status} duration={duration:.0f}ms"
        )

        # TODO: 异步写入数据库
        # 生产环境应使用后台任务或消息队列写入
        # from services.audit_service import audit_service
        # await audit_service.log(**audit_data)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP。"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def _get_safe_body(self, request: Request) -> dict:
        """安全提取请求体（排除敏感字段）。"""
        sensitive_fields = {
            "password", "token", "secret", "api_key", "credit_card",
            "session_key", "openid", "access_token",
        }

        try:
            body = await request.json()
            if isinstance(body, dict):
                return {
                    k: "***" if k.lower() in sensitive_fields else v
                    for k, v in body.items()
                }
            return {}
        except Exception:
            return {}

    def _extract_resource_type(self, path: str) -> str:
        """从路径提取资源类型。"""
        parts = path.strip("/").split("/")
        # 跳过 API 前缀 (api/v1)
        for i, part in enumerate(parts):
            if part in ("api", "v1", "api/v1"):
                continue
            return part
        return "unknown"

    def _extract_resource_id(self, path: str) -> Optional[str]:
        """从路径提取资源 ID。"""
        parts = path.strip("/").split("/")
        if len(parts) >= 4:
            # /api/v1/resource/id -> id
            return parts[-1] if not parts[-1] in ("", "active") else None
        return None

    @staticmethod
    def _method_to_action(method: str) -> str:
        """HTTP 方法映射到操作类型。"""
        mapping = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }
        return mapping.get(method, "unknown")
