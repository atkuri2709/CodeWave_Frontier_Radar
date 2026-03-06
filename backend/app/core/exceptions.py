"""Application exceptions."""


class RadarException(Exception):
    """Base exception for Frontier AI Radar."""

    def __init__(self, message: str, code: str = "RADAR_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(RadarException):
    def __init__(self, resource: str, id: str | int):
        super().__init__(f"{resource} not found: {id}", code="NOT_FOUND")


class ValidationError(RadarException):
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")
