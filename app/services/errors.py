"""User-facing error types.

Every message here is written for the pharmacist, not a programmer. The UI
shows ``str(error)`` directly, so never put technical details in these.
"""
from __future__ import annotations


class PharmaError(Exception):
    """Base class for errors that can be shown to the user as-is."""

    title = "Something needs attention"


class ValidationError(PharmaError):
    title = "Please check the details"


class DuplicateCodeError(ValidationError):
    title = "Code already in use"


class NotFoundError(PharmaError):
    title = "Not found"


class InsufficientStockError(PharmaError):
    title = "Insufficient stock"


class ExpiredStockError(PharmaError):
    title = "Expired medicine"


class InUseError(PharmaError):
    title = "Cannot remove"


class BackupError(PharmaError):
    title = "Backup / restore problem"
