"""Friendly errors: every error says what went wrong AND how to fix it."""

from __future__ import annotations


class StudioError(Exception):
    """Base error. `fix` is a plain-language hint shown to the user."""

    def __init__(self, message: str, fix: str | None = None):
        super().__init__(message)
        self.message = message
        self.fix = fix

    def friendly(self) -> str:
        text = f"\n❌  {self.message}"
        if self.fix:
            text += f"\n👉  How to fix: {self.fix}"
        return text + "\n"


class MissingKeyError(StudioError):
    def __init__(self, key_name: str, where: str):
        super().__init__(
            f"{key_name} is missing.",
            fix=(
                f"Open the .env file in the project folder and add a line "
                f"'{key_name}=your-key'. Get the key from: {where}. "
                f"See docs/SETUP_WINDOWS.md."
            ),
        )


class QuotaExceededError(StudioError):
    pass


class ToolNotFoundError(StudioError):
    pass


class GatePending(StudioError):
    """An approval gate is waiting for a human decision."""


class GateRejected(StudioError):
    """The human asked for changes at an approval gate."""


class StageNotBuiltError(StudioError):
    pass


def friendly_from_exception(exc: BaseException) -> str:
    """Turn common low-level exceptions into helpful messages."""
    if isinstance(exc, StudioError):
        return exc.friendly()
    if isinstance(exc, MemoryError):
        return StudioError(
            "Ran out of memory (RAM).",
            fix="Close other programs (browsers use a lot), try --preview mode, "
            "or lower settings in config.yaml. Your PC has 12 GB; stages are "
            "designed to stay under ~4 GB.",
        ).friendly()
    if isinstance(exc, ModuleNotFoundError):
        name = getattr(exc, "name", "a package")
        return StudioError(
            f"Python package '{name}' is not installed.",
            fix="Activate your virtual environment (.venv\\Scripts\\activate) "
            "and run: pip install -r requirements.txt",
        ).friendly()
    if isinstance(exc, KeyboardInterrupt):
        return "\n⏹  Stopped by you. Re-run the same command to continue where it stopped.\n"
    return StudioError(
        f"Unexpected error: {type(exc).__name__}: {exc}",
        fix="Check the log file in projects/<topic>/logs/run.log. Re-running "
        "resumes from the failed stage. If it keeps happening, share the log.",
    ).friendly()
