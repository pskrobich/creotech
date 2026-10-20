class UnsupportedFormatError(ValueError):
    """Raised when no adapter recognizes the payload format."""


class UnsupportedMediaTypeError(ValueError):
    """Raised when no adapter accepts the request's content type."""
