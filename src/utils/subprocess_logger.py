"""
Reader of the outputs from a subprocess.
"""

import logging
import threading
import re
from typing import IO, Optional
from typing import Protocol


logger = logging.getLogger(__name__)

class LineConsumer(Protocol):
    def __call__(self, line: str) -> None:
        ...


class SubprocessReader():
    def __init__(self, stdout: Optional[IO[str]] = None, stderr: Optional[IO[str]] = None,
                 stdout_handler: Optional[LineConsumer] = None, stderr_handler: Optional[LineConsumer] = None,
                 process_name: Optional[str] = None):
        self.process_name = process_name
        self.stdout = stdout
        self.stderr = stderr
        self.stdout_handler = stdout_handler
        self.stderr_handler = stderr_handler
        self._stop_event = threading.Event()

    def start(self) -> None:
        name = "SubprocessReader"
        if self.process_name:
            name += "-" + self.process_name
        if self.stdout:
            self.stdout_thread = threading.Thread(target=self.read_io, args=(self.stdout, self.stdout_handler, "stdout"), name=f"{name}-stdout", daemon=True)
            self.stdout_thread.start()
        if self.stderr:
            self.stderr_thread = threading.Thread(target=self.read_io, args=(self.stderr, self.stderr_handler, "stderr"), name=f"{name}-stderr", daemon=True)
            self.stderr_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def read_io(self, stream: IO[str], handler: LineConsumer, stream_name: str) -> None:
        """Monitor a single stream"""
        try:
            for line in iter(stream.readline, ''):
                if self._stop_event.is_set():
                    break

                if line:
                    # Strip the line (already decoded)
                    decoded_line = line.rstrip()
                    handler(decoded_line)
        except Exception as e:
            logger.error(f"Error reading from {stream_name}: {e}")
        finally:
            try:
                stream.close()
            except:
                pass

    def join_with_timeout(self, timeout: float = 3.0) -> bool:
        """Join the thread with a timeout."""
        if self.stdout_thread:
            self.stdout_thread.join(timeout=timeout)
        if self.stderr_thread:
            self.stderr_thread.join(timeout=timeout)
        return True


def make_log_handler(logger_to_log_to: logging.Logger, level: int, stream_name: str) -> LineConsumer:
    """Return a LineConsumer that logs each incoming line to a logger"""
    def log_handler(line: str) -> None:
        logger_to_log_to.log(level, f"[{stream_name}] {line}")
    return log_handler

class LineMatchedConsumer(Protocol):
    def __call__(self, line: str, match: re.Match[str]) -> None:
        ...


class PatternMatcher:
    def __init__(self, pattern: str, line_matched_consumer: LineMatchedConsumer):
        self.pattern = pattern
        self.line_matched_consumer = line_matched_consumer

    def create_handler(self) -> LineConsumer:
        """Create a LineConsumer that applies the pattern matching."""
        def line_matched_handler(line: str) -> None:
            match = re.search(self.pattern, line)
            if match:
                self.line_matched_consumer(line, match)
        return line_matched_handler


class DemultiplexerLineConsumer(LineConsumer):
    """Will demultiples a single line into multiple consumers"""
    def __init__(self, *consumers: LineConsumer):
        self.consumers = consumers

    def __call__(self, line: str) -> None:
        for consumer in self.consumers:
            consumer(line)


class SubprocessLogger(SubprocessReader):
    def __init__(self, stdout: Optional[IO[str]] = None, stderr: Optional[IO[str]] = None,
                 process_name: Optional[str] = None, logger: Optional[logging.Logger] = None,
                 pattern_matcher: Optional[PatternMatcher] = None):
        if not logger:
            logger = logging.getLogger()

        stdout_handler = make_log_handler(logger, logging.INFO, "stdout")
        stderr_handler = make_log_handler(logger, logging.ERROR, "stderr")
        if pattern_matcher:
            pattern_handler = pattern_matcher.create_handler()
            stdout_handler = DemultiplexerLineConsumer(stdout_handler, pattern_handler)
            stderr_handler = DemultiplexerLineConsumer(stderr_handler, pattern_handler)

        super().__init__(stdout, stderr,
                         stdout_handler,
                         stderr_handler,
                         process_name)
