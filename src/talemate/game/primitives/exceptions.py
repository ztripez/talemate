"""Exception types raised by the Game Primitives runtime."""


class PrimitiveError(ValueError):
    """Base error for invalid Game Primitives references, state, or operations."""


class InvalidAnchorRef(PrimitiveError):
    """Raised when an anchor reference string cannot be parsed or validated."""


class InvalidPrimitiveRef(PrimitiveError):
    """Raised when a primitive reference string cannot be parsed or validated."""


class PrimitiveStoreError(PrimitiveError):
    """Raised when the persisted primitive store shape is invalid."""
