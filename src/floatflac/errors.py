class FloatflacError(Exception):
    def __init__(self, code: str, message: str, fix: str) -> None:
        message = " ".join(str(message).split())
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "fix": self.fix}


def exit_code(code: str) -> int:
    return 2 if code == "usage" else 1
