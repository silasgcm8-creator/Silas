"""Repositórios: toda consulta ao banco passa por aqui."""

from app.repositories.client_repository import ClientRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.log_repository import LogRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "ClientRepository",
    "CreditRepository",
    "InstallmentRepository",
    "LogRepository",
    "PaymentRepository",
    "UserRepository",
]
