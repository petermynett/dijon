from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

import typer

_LOGGING_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure CLI-wide logging once.

    Sets up basic logging configuration for the CLI. Safe to call multiple
    times; only configures on first call.

    Args:
        level: Logging level (defaults to INFO).

    Side Effects:
        - Configures Python logging module globally.
        - Sets module-level flag to prevent reconfiguration.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    _LOGGING_CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger hooked into the shared CLI configuration.

    Args:
        name: Logger name. Uses module name if None.

    Returns:
        Configured Logger instance.

    Logs:
        None (this function only returns a logger, doesn't log itself).
    """
    return logging.getLogger(name)


@contextmanager
def handle_errors(
    operation: str,
    *,
    logger: logging.Logger | None = None,
) -> Generator[None, None, None]:
    """Provide consistent exception handling for CLI operations.

    Context manager that catches exceptions, logs them, displays user-friendly
    error messages, and exits with code 1. Re-raises typer.Exit to allow
    normal CLI exit flow.

    Args:
        operation: Human-readable operation name for error messages.
        logger: Logger instance. Defaults to module logger if None.

    Yields:
        None (used as context manager).

    Raises:
        typer.Exit: Always exits with code 1 on exception (except typer.Exit
            which is re-raised).

    Logs:
        - ERROR: "Error during {operation}" with full exception traceback.

    User Output:
        - Prints error message via typer.secho() in red: "✗ {operation} failed: {exc}".
    """
    logger = logger or get_logger(__name__)
    try:
        yield
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error during %s", operation)
        typer.secho(f"✗ {operation} failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(1) from exc


def format_result(result: Any, *, operation: str | None = None) -> str:
    """Format arbitrary result payloads into CLI-friendly text.

    Converts result objects (dict, list, bool, str, None) into formatted
    text suitable for CLI output. Handles structured results with success
    status, statistics, failures, and items.

    Args:
        result: Result object to format. Can be dict, list, bool, str,
            or None.
        operation: Optional operation name to include in formatted output.

    Returns:
        Formatted string ready for CLI display.
    """
    op_label = operation or "Result"

    if result is None:
        return f"✓ {op_label}"

    if isinstance(result, bool):
        icon = "✓" if result else "✗"
        return f"{icon} {op_label}"

    if isinstance(result, str):
        return f"{op_label}: {result}"

    if isinstance(result, list):
        rendered_items = "\n".join(f"  • {item}" for item in result)
        return f"{op_label}:\n{rendered_items}" if rendered_items else f"{op_label}: []"

    if isinstance(result, dict):
        return _format_result_dict(result, op_label)

    return f"{op_label}: {result!r}"




class BaseCLI:
    """Utility base class for CLI command groups."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.logger = get_logger(__name__)

    def handle_cli_operation(
        self,
        *,
        operation: str,
        op_callable: Callable[[], Any],
        pre_message: str | None = None,
        success_message: str | None = None,
    ) -> Any:
        """Run an operation with consistent logging, formatting, and errors.

        Executes a callable operation with standardized error handling,
        logging, and result formatting. Displays pre-message before execution
        and optional success message after.

        Args:
            operation: Human-readable operation name for error handling.
            op_callable: Callable that performs the operation and returns
                a result.
            pre_message: Optional message to display before operation starts.
            success_message: Optional message to display if operation succeeds
                (only shown if result is a dict with success=True).

        Returns:
            Result from op_callable.

        User Output:
            - Prints pre_message via typer.echo() if provided.
            - Prints success_message via typer.echo() if operation succeeds
                and result is a dict with success=True.
            - Prints formatted result via typer.echo().
            - Error messages handled by handle_errors context manager.

        Logs:
            - Delegates to handle_errors for exception logging.
        """
        if pre_message:
            typer.echo(pre_message)

        with handle_errors(operation, logger=self.logger):
            result = op_callable()

        if success_message and isinstance(result, dict) and result.get("success"):
            typer.echo(success_message)

        typer.echo(format_result(result, operation=operation))
        return result


def run_cli_task(task: Callable[[], int | None]) -> int:
    """Run a CLI task and convert unexpected failures into exit codes.

    Executes a task function and ensures it returns an integer exit code.
    Catches exceptions and converts them to exit code 1.

    Args:
        task: Callable that returns an integer exit code or None.

    Returns:
        Integer exit code (0 for success, 1 for failure).

    Logs:
        - ERROR: "Unhandled error during CLI task" with exception details
            if task raises an exception.
    """
    logger = get_logger(__name__)
    try:
        result = task()
        return int(result) if result is not None else 0
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error during CLI task")
        return 1


def _format_result_dict(result: dict[str, Any], op_label: str) -> str:
    """Format a dictionary result into CLI-friendly text.

    Formats structured result dictionaries with success status, statistics,
    messages, failures, and items into a multi-line formatted string.

    Args:
        result: Result dictionary with optional keys: success, total,
            succeeded, failed, skipped, elapsed_s, message, failures, items.
        op_label: Operation label to display.

    Returns:
        Formatted multi-line string.
    """
    icon = "✓" if result.get("success", True) else "✗"
    lines = [f"{icon} {op_label}"]

    stats_order = [
        ("total", "total"),
        ("succeeded", "succeeded"),
        ("failed", "failed"),
        ("skipped", "skipped"),
    ]
    stats = [
        f"{label}: {result[key]}"
        for key, label in stats_order
        if key in result and result[key] is not None
    ]
    if "elapsed_s" in result:
        stats.append(f"elapsed: {result['elapsed_s']:.2f}s")
    if stats:
        lines.append("  " + " | ".join(stats))

    message = result.get("message")
    if message:
        lines.append(f"  ℹ {message}")

    failures = result.get("failures") or []
    if failures:
        lines.append("  Failures:")
        for failure in failures:
            item = failure.get("item", "item")
            reason = failure.get("reason") or failure.get("error") or "Unknown error"
            lines.append(f"    • {item}: {reason}")

    items = result.get("items") or []
    if items:
        lines.append("  Items:")
        for item in items:
            if isinstance(item, dict):
                name = item.get("item") or item.get("file") or item.get("id", "item")
                status = item.get("status") or (
                    "success" if item.get("success", True) else "failed"
                )
                detail = item.get("detail") or item.get("error") or ""
                extra = f" ({detail})" if detail else ""
                lines.append(f"    • {name}: {status}{extra}")
            else:
                lines.append(f"    • {item}")

    return "\n".join(lines)

