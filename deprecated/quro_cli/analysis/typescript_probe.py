"""
TypeScript Probe - Python wrapper for symbol_probe.js

Manages subprocess communication with the TypeScript probe via JSON-RPC over stdio.
Provides async interface for type analysis operations.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TypeInfo:
    """Type information result"""
    type_string: str
    fingerprint: Optional[str]
    kind: str
    symbol_name: Optional[str] = None
    flags: Optional[int] = None


@dataclass
class DefinitionLocation:
    """Symbol definition location"""
    file_path: str
    line: int
    character: int
    fingerprint: Optional[str]
    symbol_name: str
    kind: str


@dataclass
class Diagnostic:
    """TypeScript diagnostic"""
    category: str
    code: int
    message: str
    location: Optional[Dict[str, int]] = None


class TypeScriptProbeError(Exception):
    """Base exception for TypeScript probe errors"""
    pass


class TypeScriptProbe:
    """
    Python wrapper for symbol_probe.js

    Manages subprocess lifecycle and JSON-RPC communication.
    """

    def __init__(self, tsconfig_path: Optional[str] = None):
        """
        Initialize TypeScript probe

        Args:
            tsconfig_path: Path to tsconfig.json (optional, defaults to project root)
        """
        self.tsconfig_path = tsconfig_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._ready = False

    async def start(self):
        """Start the TypeScript probe subprocess"""
        if self.process is not None:
            logger.warning("TypeScript probe already started")
            return

        # Find symbol_probe.cjs (now in same directory)
        probe_path = Path(__file__).parent / "symbol_probe.cjs"
        if not probe_path.exists():
            raise TypeScriptProbeError(f"symbol_probe.cjs not found at {probe_path}")

        # Start subprocess
        try:
            self.process = await asyncio.create_subprocess_exec(
                "node",
                str(probe_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_responses())

            # Wait for probe_ready notification
            await asyncio.sleep(0.2)  # Give probe time to start

            # Mark as ready before calling initialize (needed for _call_method)
            self._ready = True

            # Initialize with tsconfig
            init_result = await self._call_method("initialize", {
                "tsconfigPath": self.tsconfig_path
            })

            if not init_result.get("ok"):
                self._ready = False
                raise TypeScriptProbeError(f"Probe initialization failed: {init_result.get('error')}")

            logger.info("TypeScript probe started successfully")

        except Exception as e:
            await self.stop()
            raise TypeScriptProbeError(f"Failed to start TypeScript probe: {e}")

    async def stop(self):
        """Stop the TypeScript probe subprocess"""
        if self.process is None:
            return

        try:
            # Cancel reader task
            if self._reader_task:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            # Terminate process
            if self.process.stdin and not self.process.stdin.is_closing():
                self.process.stdin.close()
                try:
                    await self.process.stdin.wait_closed()
                except Exception:
                    pass

            # Check if process is still running
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("TypeScript probe did not terminate gracefully, killing")
                    self.process.kill()
                    await self.process.wait()

        except ProcessLookupError:
            # Process already terminated
            pass
        except Exception as e:
            logger.error(f"Error stopping TypeScript probe: {e}")

        finally:
            self.process = None
            self._ready = False
            logger.info("TypeScript probe stopped")

    async def get_type_at_position(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> TypeInfo:
        """
        Get type information at a specific position

        Args:
            file_path: Absolute file path
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            TypeInfo object

        Raises:
            TypeScriptProbeError: If probe returns error
        """
        result = await self._call_method("get_type_at_position", {
            "filePath": file_path,
            "line": line,
            "character": character
        })

        if "error" in result:
            raise TypeScriptProbeError(
                f"Type analysis failed: {result['error']} "
                f"(fallback: {result.get('fallback', 'none')})"
            )

        return TypeInfo(
            type_string=result["typeString"],
            fingerprint=result.get("fingerprint"),
            kind=result["kind"],
            symbol_name=result.get("symbolName"),
            flags=result.get("flags")
        )

    async def find_definition(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> DefinitionLocation:
        """
        Find definition location for a symbol

        Args:
            file_path: Absolute file path
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            DefinitionLocation object

        Raises:
            TypeScriptProbeError: If probe returns error
        """
        result = await self._call_method("find_definition", {
            "filePath": file_path,
            "line": line,
            "character": character
        })

        if "error" in result:
            raise TypeScriptProbeError(
                f"Definition lookup failed: {result['error']} "
                f"(fallback: {result.get('fallback', 'none')})"
            )

        return DefinitionLocation(
            file_path=result["filePath"],
            line=result["line"],
            character=result["character"],
            fingerprint=result.get("fingerprint"),
            symbol_name=result["symbolName"],
            kind=result["kind"]
        )

    async def resolve_import_path(
        self,
        file_path: str,
        import_path: str
    ) -> str:
        """
        Resolve import path to absolute file path

        Args:
            file_path: Source file path
            import_path: Import specifier (e.g., './foo', '@/bar')

        Returns:
            Resolved absolute file path

        Raises:
            TypeScriptProbeError: If resolution fails
        """
        result = await self._call_method("resolve_import_path", {
            "filePath": file_path,
            "importPath": import_path
        })

        if "error" in result:
            raise TypeScriptProbeError(
                f"Import resolution failed: {result['error']} "
                f"(fallback: {result.get('fallback', 'none')})"
            )

        return result["resolvedPath"]

    async def get_diagnostics(self, file_path: str) -> List[Diagnostic]:
        """
        Get diagnostics for a file

        Args:
            file_path: Absolute file path

        Returns:
            List of Diagnostic objects
        """
        result = await self._call_method("get_diagnostics", {
            "filePath": file_path
        })

        diagnostics = result.get("diagnostics", [])
        return [
            Diagnostic(
                category=d["category"],
                code=d["code"],
                message=d["message"],
                location=d.get("location")
            )
            for d in diagnostics
        ]

    async def ping(self) -> bool:
        """
        Ping the probe to check if it's alive

        Returns:
            True if probe responds
        """
        try:
            result = await self._call_method("ping", {})
            return result.get("pong") is True
        except Exception:
            return False

    async def extract_call_graph(self, file_path: str) -> Dict[str, List[str]]:
        """
        Extract call graph from TypeScript/JavaScript file.

        Args:
            file_path: Absolute file path

        Returns:
            Dict mapping function name to list of called functions
        """
        result = await self._call_method("extract_call_graph", {
            "filePath": file_path
        })

        if "error" in result:
            logger.warning(f"Call graph extraction failed: {result.get('error')}")
            return {}

        # Build calls_by_function mapping
        calls_by_function: Dict[str, List[str]] = {}
        for call in result.get("calls", []):
            caller = call.get("caller")
            callee = call.get("callee")
            if caller and callee:
                if caller not in calls_by_function:
                    calls_by_function[caller] = []
                calls_by_function[caller].append(callee)

        return calls_by_function

    # === Internal Methods ===

    async def _call_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call JSON-RPC method on the probe

        Args:
            method: Method name
            params: Method parameters

        Returns:
            Result dictionary

        Raises:
            TypeScriptProbeError: If probe is not ready or call fails
        """
        if not self._ready or self.process is None:
            raise TypeScriptProbeError("TypeScript probe not ready")

        # Generate request ID
        self.request_id += 1
        request_id = self.request_id

        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        # Send request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        try:
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()

            # Wait for response (with timeout)
            result = await asyncio.wait_for(future, timeout=10.0)
            return result

        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TypeScriptProbeError(f"Request timeout: {method}")

        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise TypeScriptProbeError(f"Request failed: {e}")

    async def _read_responses(self):
        """Background task to read responses from probe"""
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    response = json.loads(line.decode())

                    # Handle notification (no id)
                    if "id" not in response:
                        method = response.get("method")
                        if method == "probe_ready":
                            logger.info("TypeScript probe ready")
                        elif method == "program_updated":
                            logger.debug("TypeScript program updated")
                        continue

                    # Handle response
                    request_id = response["id"]
                    future = self.pending_requests.pop(request_id, None)

                    if future and not future.done():
                        if "error" in response:
                            future.set_exception(
                                TypeScriptProbeError(response["error"]["message"])
                            )
                        else:
                            future.set_result(response["result"])

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from probe: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading probe responses: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
