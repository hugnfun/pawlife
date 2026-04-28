"""
审计日志模型。

记录所有关键操作的审计追踪。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class AuditLog(Base):
    """审计日志表。

    记录用户的关键操作，用于安全审计和操作追踪。
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)
    action = Column(String(50), nullable=False, comment="操作类型: create/update/delete/login/logout")
    resource_type = Column(String(50), nullable=False, comment="资源类型: pet/meal/family/user")
    resource_id = Column(String(36), nullable=True, comment="资源 ID")
    detail = Column(JSONB, nullable=True, comment="操作详情（请求/响应关键字段）")
    ip_address = Column(String(45), nullable=True, comment="客户端 IP")
    user_agent = Column(String(500), nullable=True, comment="User-Agent")
    status = Column(String(20), default="success", comment="操作结果: success/failure")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
