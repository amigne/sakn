import asyncio
import logging
import os
import signal
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SubprocessResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timed_out: bool = False
    killed_by_signal: int | None = None


class SubprocessExecutor:
    """Sandboxed subprocess runner for network tools.

    Constraints:
    - Popen with list args (never shell=True)
    - asyncio.wait_for timeout
    - Process group for clean child termination
    - SIGTERM → SIGKILL escalation
    - stderr logged but not exposed to user
    """

    def __init__(self, hard_timeout: float = 300.0):
        self._hard_timeout = hard_timeout

    async def run(self, args: list[str], timeout: float | None = None) -> SubprocessResult:
        effective_timeout = min(timeout or self._hard_timeout, self._hard_timeout)
        start = time.monotonic()

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout,
            )
            duration_ms = (time.monotonic() - start) * 1000
            exit_code = process.returncode or 0

            if stderr_bytes:
                logger.info(
                    "subprocess stderr",
                    extra={"args": args, "stderr": stderr_bytes.decode("utf-8", errors="replace")[:500]},
                )

            return SubprocessResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            await self._kill_process(process)
            return SubprocessResult(
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=duration_ms,
                timed_out=True,
            )

        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            await self._kill_process(process)
            return SubprocessResult(
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=duration_ms,
            )

    async def _kill_process(self, process: asyncio.subprocess.Process) -> None:
        try:
            if process.returncode is None:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
        except ProcessLookupError:
            pass
