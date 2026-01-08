from fastapi import HTTPException, status

class AppError(HTTPException):
    def __init__(self, status_code: int, message: str, code: str = None):
        super().__init__(status_code=status_code, detail={"message": message, "code": code or str(status_code)})

class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, message=message, code="401")

class NotFoundError(AppError):
    def __init__(self, message: str = "Not Found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, message=message, code="404")

class BadRequestError(AppError):
    def __init__(self, message: str = "Bad Request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, message=message, code="400")

class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, message=message, code="403")
