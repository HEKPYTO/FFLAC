import json
import sys

from .errors import exit_code

COMPATIBILITY_WARNING = "This stream uses an experimental float extension. Standard FLAC decoders will refuse it. Keep a `floatflac` build to decode it."


def emit_json(command: str, data=None, error=None) -> None:
    print(
        json.dumps(
            {
                "schema": "floatflac/v1",
                "command": command,
                "data": data,
                "error": error,
            },
            separators=(",", ":"),
        )
    )


def emit_error(command: str, err, as_json: bool) -> int:
    if as_json:
        emit_json(command, None, err.as_dict())
    else:
        print(f"{err.code}: {err.message}", file=sys.stderr)
        print(f"fix: {err.fix}", file=sys.stderr)
    return exit_code(err.code)


def compatibility_warning() -> str:
    return COMPATIBILITY_WARNING
