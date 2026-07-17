from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document")

class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    number: Mapped[int] = mapped_column(Integer)
    source_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    document: Mapped[Document] = relationship(back_populates="versions")
    nodes: Mapped[list["NodeSnapshot"]] = relationship(back_populates="version")

class LogicalNode(Base):
    __tablename__ = "logical_nodes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    identity_path: Mapped[str] = mapped_column(Text)

class NodeSnapshot(Base):
    __tablename__ = "node_snapshots"
    __table_args__ = (UniqueConstraint("version_id", "logical_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    logical_id: Mapped[str] = mapped_column(ForeignKey("logical_nodes.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id"), index=True)
    parent_logical_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    heading: Mapped[str] = mapped_column(String(500))
    level: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    full_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    position: Mapped[int] = mapped_column(Integer)
    version: Mapped[DocumentVersion] = relationship(back_populates="nodes")

class Selection(Base):
    __tablename__ = "selections"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    items: Mapped[list["SelectionItem"]] = relationship(cascade="all, delete-orphan")

class SelectionItem(Base):
    __tablename__ = "selection_items"
    __table_args__ = (UniqueConstraint("selection_id", "snapshot_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"))
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("node_snapshots.id"))
    snapshot: Mapped[NodeSnapshot] = relationship()
