from __future__ import annotations

import logging
import os
import sys
import traceback
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any, TextIO

import typer

from ..global_config import DERIVED_LOGS_DIR

_LOGGING_CONFIGURED = False


def _get_dijon_version() -> str:
    try:
        return version("dijon")
    except Exception:  # noqa: BLE001
        return "unknown"


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
    log_file: TextIO | None = None,
) -> Generator[None, None, None]:
    """Provide consistent exception handling for CLI operations.

    Context manager that catches exceptions, logs them, displays user-friendly
    error messages, and exits with code 1. Re-raises typer.Exit to allow
    normal CLI exit flow.

    Args:
        operation: Human-readable operation name for error messages.
        logger: Logger instance. Defaults to module logger if None.
        log_file: Optional file handle to write error message and traceback.

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
        if log_file:
            log_file.write(f"\n✗ {operation} failed: {exc}\n")
            log_file.write(f"exception_type: {type(exc).__name__}\n")
            log_file.write(f"exception_message: {exc}\n")
            log_file.write("traceback:\n")
            log_file.write(traceback.format_exc())
            log_file.flush()
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
        log_module: str | None = None,
        log_method: str | None = None,
        log_dry_run: bool = False,
        enable_log: bool = True,
        log_context: dict[str, Any] | None = None,
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
            log_module: Module name for log filename (e.g. novelty, tempogram).
            log_method: Method name for log filename (e.g. spectrum, fourier).
            log_dry_run: Whether this run is a dry run (for filename).
            enable_log: Whether to write to a log file (default True).
            log_context: Extra key-value pairs for metadata header.

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
        log_file: TextIO | None = None
        use_log = enable_log and log_module is not None

        def _out(msg: str) -> None:
            typer.echo(msg)
            if log_file:
                log_file.write(msg + "\n")
                log_file.flush()

        if use_log:
            DERIVED_LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%I-%M-%S")
            parts = [ts, log_module]
            if log_method:
                parts.append(log_method)
            if log_dry_run:
                parts.append("dryrun")
            log_path = DERIVED_LOGS_DIR / f"{'_'.join(parts)}.log"
            log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
            header_lines = [
                "--- metadata ---",
                f"timestamp: {datetime.now(timezone.utc).isoformat()}",
                f"command: {log_module}",
                f"argv: {sys.argv}",
                f"cwd: {os.getcwd()}",
                f"dijon_version: {_get_dijon_version()}",
                f"python_version: {sys.version}",
            ]
            ctx = log_context or {}
            for k, v in ctx.items():
                header_lines.append(f"{k}: {v}")
            header_lines.append("---")
            log_file.write("\n".join(header_lines) + "\n")
            log_file.flush()

        try:
            if pre_message:
                _out(pre_message)

            with handle_errors(operation, logger=self.logger, log_file=log_file):
                result = op_callable()

            if success_message and isinstance(result, dict) and result.get("success"):
                _out(success_message)

            _out(format_result(result, operation=operation))
            return result
        finally:
            if log_file:
                log_file.close()


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
                # For tempogram-style items, include output on the main line.
                # For beats-style items, show both inputs and output.
                output_name = item.get("output")
                is_meter = item.get("kind") == "meter"
                is_tempogram = "tempo_bin_count" in item and "feature_sample_rate_hz" in item
                is_beats = "num_beats" in item and "input_novelty" in item
                if is_meter and output_name:
                    lines.append(f"    • {name}: {status} -> output: {output_name}{extra}")
                elif is_beats and output_name:
                    inp_tempo = item.get("input_tempogram") or name
                    inp_nov = item.get("input_novelty", "")
                    lines.append(f"    • {inp_tempo}, {inp_nov}: {status} -> {output_name}{extra}")
                elif is_tempogram and output_name:
                    lines.append(f"    • {name}: {status} -> {output_name}{extra}")
                else:
                    lines.append(f"    • {name}: {status}{extra}")
                novelty_details = _format_novelty_item_details(item)
                if novelty_details:
                    lines.append(f"      {novelty_details}")
                tempogram_details = _format_tempogram_item_details(item)
                if tempogram_details:
                    for line in tempogram_details:
                        lines.append(f"      {line}")
                beats_details = _format_beats_item_details(item)
                if beats_details:
                    for line in beats_details:
                        lines.append(f"      {line}")
                meter_details = _format_meter_item_details(item)
                if meter_details:
                    for line in meter_details:
                        lines.append(f"      {line}")
            else:
                lines.append(f"    • {item}")

    # Show items that would be deleted in dry-run mode
    if result.get("dry_run") and result.get("items_to_delete"):
        lines.append("  Items that would be deleted:")
        for item in result["items_to_delete"]:
            lines.append(f"    {item}")

    return "\n".join(lines)


def _format_novelty_item_details(item: dict[str, Any]) -> str | None:
    """Format optional novelty item details for CLI display."""
    marker_start = item.get("start_marker")
    marker_end = item.get("end_marker")
    start_sec = item.get("start_sec")
    end_sec = item.get("end_sec")
    num_features = item.get("num_features")
    novelty_fs_hz = item.get("novelty_sample_rate_hz")
    output = item.get("output")

    if (
        marker_start is None
        or marker_end is None
        or start_sec is None
        or end_sec is None
        or num_features is None
        or novelty_fs_hz is None
        or output is None
    ):
        return None

    return (
        f"markers: {marker_start} -> {marker_end} | "
        f"region: {start_sec:.3f}s -> {end_sec:.3f}s | "
        f"features: {num_features} @ {novelty_fs_hz:.3f} Hz | "
        f"output: {output}"
    )


def _format_tempogram_item_details(item: dict[str, Any]) -> list[str] | None:
    """Format optional tempogram item details as one compact line for CLI display."""
    num_features = item.get("num_features")
    feature_fs = item.get("feature_sample_rate_hz")
    N = item.get("N")
    H = item.get("H")
    shape = item.get("shape")
    dtype = item.get("dtype")
    tempo_res = item.get("tempo_resolution_bpm")
    tempo_bins = item.get("tempo_bin_count")

    if (
        num_features is None
        or feature_fs is None
        or N is None
        or H is None
        or shape is None
        or dtype is None
        or tempo_res is None
        or tempo_bins is None
    ):
        return None

    line = (
        f"feat: n={num_features} fs={feature_fs}Hz | "
        f"win: N={N} H={H} | "
        f"arr: shape={shape} dtype={dtype} | "
        f"tempo: d={tempo_res:.2f} bins={tempo_bins}"
    )
    return [line]


def _format_beats_item_details(item: dict[str, Any]) -> list[str] | None:
    """Format optional beats item details as one compact line for CLI display."""
    num_beats = item.get("num_beats")
    bpm = item.get("implied_bpm")
    shape = item.get("shape")
    dtype = item.get("dtype")
    ibi_min = item.get("ibi_min")
    ibi_max = item.get("ibi_max")
    ibi_mean = item.get("ibi_mean")
    ibi_std = item.get("ibi_std")
    t_first = item.get("t_first")
    t_last = item.get("t_last")
    duration = item.get("duration")
    coverage = item.get("coverage_ratio")

    if (
        num_beats is None
        or bpm is None
        or shape is None
        or dtype is None
        or ibi_min is None
        or ibi_max is None
        or ibi_mean is None
        or ibi_std is None
        or t_first is None
        or t_last is None
        or duration is None
        or coverage is None
    ):
        return None

    line = (
        f"beats: n={num_beats} | bpm={bpm:.1f} | "
        f"arr: shape={shape} dtype={dtype} "
        f"min/max/mean/std={ibi_min:.3g}/{ibi_max:.3g}/{ibi_mean:.3g}/{ibi_std:.3g} | "
        f"t0={t_first:.3g} tLast={t_last:.3g} dur={duration:.3g} | coverage={coverage:.3g}"
    )
    return [line]


def _format_meter_item_details(item: dict[str, Any]) -> list[str] | None:
    """Format optional meter item details as two compact lines for CLI display."""
    head_in = item.get("head_in")
    num_beats = item.get("num_beats")
    t_first = item.get("t_first_beat")
    t_last = item.get("t_last_beat")
    bpb = item.get("beats_per_bar")
    label_shape = item.get("label_shape")
    bar_count = item.get("bar_count")
    beat_counts = item.get("beat_counts")
    nearest = item.get("head_in_nearest_beat")
    offset = item.get("head_in_offset")

    if (
        head_in is None
        or num_beats is None
        or t_first is None
        or t_last is None
        or bpb is None
        or label_shape is None
        or bar_count is None
        or beat_counts is None
        or nearest is None
        or offset is None
    ):
        return None

    return [
        f"head_in={head_in:.3f}s | beats: {num_beats} ({t_first:.3f}s→{t_last:.3f}s) | "
        f"beats_per_bar={bpb} | label_shape={label_shape}",
        f"bar_count={bar_count} | beat_counts={beat_counts} | "
        f"head_in_nearest_beat={nearest:.3f}s (offset={offset:+.3f}s)",
    ]

