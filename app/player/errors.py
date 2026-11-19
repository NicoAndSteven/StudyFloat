"""User-facing errors. Messages are already in plain Chinese — never show stack traces."""


class StudyFloatError(Exception):
    """Base class for all errors safe to display to the user."""


class InvalidUrlError(StudyFloatError):
    pass


class ParseError(StudyFloatError):
    """Bilibili parsing failed; message is already user-friendly."""


class CookieRejectedError(ParseError):
    pass


class NetworkError(ParseError):
    pass


class PlayerStartError(StudyFloatError):
    pass


class MpvCommandError(StudyFloatError):
    pass
