class ServiceException(Exception):
    """Base service exception."""


class ObjectNotFound(ServiceException):
    """Raised when an object cannot be found."""


class RequestValidation(ServiceException):
    """Raised when request data is invalid."""
