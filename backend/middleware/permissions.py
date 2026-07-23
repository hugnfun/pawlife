"""
RBAC 权限中间件。

基于角色的访问控制，支持 OWNER / ADMIN / MEMBER 三种角色。
权限矩阵定义在 PERMISSIONS 字典中。
"""

import logging
from typing import Dict, Optional, Set

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 权限矩阵: {role: {resource: Set[actions]}}
# actions: "read", "create", "update", "delete", "manage"
PERMISSIONS: Dict[str, Dict[str, Set[str]]] = {
    "OWNER": {
        "pet": {"read", "create", "update", "delete"},
        "family": {"read", "create", "update", "delete", "manage", "invite"},
        "meal": {"read", "create", "update", "delete"},
        "health_report": {"read", "create"},
        "reminder": {"read", "create", "update", "delete"},
        "user": {"read", "update"},
        "audit": {"read"},
    },
    "ADMIN": {
        "pet": {"read", "create", "update"},
        "family": {"read", "invite"},
        "meal": {"read", "create", "update"},
        "health_report": {"read", "create"},
        "reminder": {"read", "create", "update"},
        "user": {"read"},
        "audit": set(),
    },
    "MEMBER": {
        "pet": {"read"},
        "family": {"read"},
        "meal": {"read", "create"},
        "health_report": {"read"},
        "reminder": {"read"},
        "user": {"read"},
        "audit": set(),
    },
}

# 默认角色权限（未加入家庭组的用户）
DEFAULT_PERMISSIONS = PERMISSIONS["OWNER"]

# 路由到资源和操作的映射
# 格式: (path_pattern, {method: (resource, action)})
ROUTE_PERMISSIONS = [
    # 宠物管理
    ("/pets", {
        "GET": ("pet", "read"),
        "POST": ("pet", "create"),
    }),
    ("/pets/", {
        "GET": ("pet", "read"),
        "PUT": ("pet", "update"),
        "DELETE": ("pet", "delete"),
    }),
    # 家庭管理
    ("/families", {
        "GET": ("family", "read"),
        "POST": ("family", "create"),
    }),
    ("/families/join", {
        "POST": ("family", "create"),
    }),
    ("/families/", {
        "GET": ("family", "read"),
    }),
    ("/families/{family_id}/invite", {
        "GET": ("family", "invite"),
    }),
    ("/families/{family_id}/members", {
        "GET": ("family", "read"),
    }),
    # 饮食记录
    ("/logs/meals", {
        "GET": ("meal", "read"),
        "POST": ("meal", "create"),
    }),
    ("/logs/meals/", {
        "PUT": ("meal", "update"),
        "DELETE": ("meal", "delete"),
    }),
    # 健康报告
    ("/ai/health-report", {
        "POST": ("health_report", "create"),
    }),
    # 提醒
    ("/reminders", {
        "GET": ("reminder", "read"),
        "POST": ("reminder", "create"),
    }),
    ("/reminders/", {
        "PUT": ("reminder", "update"),
        "DELETE": ("reminder", "delete"),
    }),
]

# 公开路由（不需要权限检查）
PUBLIC_PATHS = {
    "/health", "/", "/api/info", "/docs", "/redoc", "/api/openapi.json",
    "/auth/wechat/login", "/auth/refresh",
}


class PermissionMiddleware(BaseHTTPMiddleware):
    """RBAC 权限中间件。

    检查当前用户的角色是否有权访问请求的资源。
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 跳过公开路由
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # 跳过 OPTIONS 请求（CORS preflight）
        if request.method == "OPTIONS":
            return await call_next(request)

        # 获取用户角色（从 request.state，由 auth middleware 设置）
        user_role = getattr(request.state, "user_role", None)

        # 如果没有角色信息，跳过权限检查（由具体路由处理）
        if not user_role:
            return await call_next(request)

        # 查找匹配的路由权限
        matched_permission = self._match_permission(path, request.method)

        if not matched_permission:
            # 未匹配到权限规则，放行
            return await call_next(request)

        resource, action = matched_permission
        role_permissions = PERMISSIONS.get(user_role, DEFAULT_PERMISSIONS)
        resource_perms = role_permissions.get(resource, set())

        if action not in resource_perms:
            logger.warning(
                f"权限不足: user_role={user_role}, "
                f"resource={resource}, action={action}, "
                f"path={path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "message": f"权限不足，无法执行 {action} 操作",
                    "required": action,
                    "resource": resource,
                },
            )

        return await call_next(request)

    def _match_permission(self, path: str, method: str) -> Optional[tuple]:
        """匹配路由权限规则。"""
        for pattern, methods in ROUTE_PERMISSIONS:
            if method in methods:
                # 精确匹配或前缀匹配
                if path == pattern or path.startswith(pattern):
                    return methods[method]

                # 带路径参数的匹配（如 /pets/{id}）
                pattern_parts = pattern.rstrip("/").split("/")
                path_parts = path.rstrip("/").split("/")

                if len(pattern_parts) == len(path_parts):
                    match = True
                    for pp, pathp in zip(pattern_parts, path_parts):
                        if pp.startswith("{"):
                            continue
                        if pp != pathp:
                            match = False
                            break
                    if match:
                        return methods[method]

        return None
