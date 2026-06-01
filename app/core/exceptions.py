"""Application exceptions."""


class BaseServiceError(Exception):
    """Base service-layer exception."""


class NotFoundError(BaseServiceError):
    """Raised when a requested entity does not exist."""


class AlreadyExistError(BaseServiceError):
    """Raised when an entity already exists."""
