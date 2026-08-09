"""Camada de acesso ao banco de dados."""

from app.database.connection import get_engine, session_scope

__all__ = ["get_engine", "session_scope"]
