"""Run the CCTV-based attendance system."""

from __future__ import annotations

import argparse
import threading
import time
from typing import List

from src import config
from src.cctv_stream_processor import CCTVStreamProcessor


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Smart Attendance CCTV processor(s) for entry/exit streams.",
    )
    parser.add_argument(
        "--mode",
        choices=("entry", "exit", "both"),
        default="both",
        help="Which processor(s) to run.",
    )
    parser.add_argument(
        "--entry-stream",
        default=None,
        help="Entry camera stream URL/device ID. Defaults to ENTRY_CAMERA_STREAM or CCTV_STREAM_URL.",
    )
    parser.add_argument(
        "--exit-stream",
        default=None,
        help="Exit camera stream URL/device ID. Defaults to EXIT_CAMERA_STREAM.",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Optional fixed subject override for CCTV marking.",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable OpenCV windows and run in headless mode.",
    )
    return parser.parse_args()


def _resolve_streams(args: argparse.Namespace) -> tuple[str, str]:
    entry_stream = (
        str(args.entry_stream).strip()
        if args.entry_stream is not None
        else (config.ENTRY_CAMERA_STREAM or config.CCTV_STREAM_URL)
    )
    exit_stream = (
        str(args.exit_stream).strip()
        if args.exit_stream is not None
        else (config.EXIT_CAMERA_STREAM or "")
    )

    if args.mode == "entry":
        exit_stream = ""
    elif args.mode == "exit":
        entry_stream = ""

    return entry_stream.strip(), exit_stream.strip()


def _create_processors(
    args: argparse.Namespace,
    entry_stream: str,
    exit_stream: str,
) -> List[CCTVStreamProcessor]:
    show_display = not args.no_display
    processors: List[CCTVStreamProcessor] = []

    if entry_stream:
        processors.append(
            CCTVStreamProcessor(
                stream_url=entry_stream,
                camera_role="entry",
                camera_name="Entry CCTV",
                subject=args.subject,
                show_live_display=show_display,
            )
        )

    if exit_stream:
        processors.append(
            CCTVStreamProcessor(
                stream_url=exit_stream,
                camera_role="exit",
                camera_name="Exit CCTV",
                subject=args.subject,
                show_live_display=show_display,
            )
        )

    return processors


def main() -> int:
    args = _parse_args()
    entry_stream, exit_stream = _resolve_streams(args)
    processors = _create_processors(args, entry_stream, exit_stream)

    if not processors:
        print("No CCTV streams configured.")
        print("Set SMART_ATTENDANCE_ENTRY_CAMERA_STREAM / SMART_ATTENDANCE_EXIT_CAMERA_STREAM")
        print("or use --entry-stream / --exit-stream explicitly.")
        return 1

    stop_event = threading.Event()
    threads = [processor.run_in_thread(stop_event=stop_event) for processor in processors]

    print("=" * 72)
    print("SMART ATTENDANCE CCTV SYSTEM")
    print("=" * 72)
    print(f"Mode               : {args.mode}")
    print(f"Entry stream       : {entry_stream or 'N/A'}")
    print(f"Exit stream        : {exit_stream or 'N/A'}")
    print(f"Frame interval     : {config.FRAME_PROCESS_INTERVAL}")
    print(f"Confidence >=      : {config.RECOGNITION_CONFIDENCE_THRESHOLD:.2f}%")
    print(f"Duplicate window   : {config.DUPLICATE_ATTENDANCE_WINDOW_SECONDS}s")
    print(f"Live display       : {'ON' if not args.no_display else 'OFF'}")
    if args.subject:
        print(f"Subject override   : {args.subject}")
    print("Press Ctrl+C to stop all processors.")
    print("=" * 72)

    try:
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutdown requested. Stopping CCTV processors...")
    finally:
        stop_event.set()
        for processor in processors:
            processor.stop()
        for thread in threads:
            thread.join(timeout=5.0)
        print("CCTV system stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
