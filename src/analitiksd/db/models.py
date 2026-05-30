# src/analitiksd/db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analitiksd.db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles", back_populates="users"
    )


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )
    sources: Mapped[list["DataSource"]] = relationship(
        secondary="role_sources", back_populates="roles"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(16))  # mcp | sql
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    roles: Mapped[list["Role"]] = relationship(
        secondary="role_sources", back_populates="sources"
    )


class RoleSource(Base):
    __tablename__ = "role_sources"
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True
    )


class ReportPerm(Base):
    __tablename__ = "report_perms"
    id: Mapped[int] = mapped_column(primary_key=True)
    # FK на reports появится миграцией в Плане 4; пока просто индексированный id
    report_id: Mapped[int] = mapped_column(index=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE")
    )
    access: Mapped[str] = mapped_column(String(8))  # view | edit
