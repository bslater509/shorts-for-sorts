"""Domain exceptions shared across the pipeline."""


class BatchCancelledError(Exception):
    """Raised when a batch worker is interrupted by an explicit cancel request."""
