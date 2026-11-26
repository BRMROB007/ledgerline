class DomainError(Exception):
    status = 400
    code = "invalid_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status = 404
    code = "not_found"


class Conflict(DomainError):
    status = 409
    code = "conflict"


class Unprocessable(DomainError):
    status = 422
    code = "unprocessable"
