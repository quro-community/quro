"""Phantom Orchestrator - Bridges Shadow Adapter and Phantom Kernel.

@module quro.orchestrators.phantom
@intent Coordinate Monte Carlo simulation and shadow file persistence.
"""

from typing import Tuple, Optional, List
from core.phantom import (
    PhantomKernel,
    ThreadSequence,
    PhantomResult,
    SimulationConfig,
    Atom,
)
from adapters.shadows import (
    ShadowAdapter,
    ShadowFile,
    ShadowReadRequest,
    ShadowWriteRequest,
    DSLAtom,
)


class PhantomOrchestrator:
    """Orchestrates Monte Carlo simulation and shadow file persistence.

    Coordinates:
    - Phantom Kernel (pure computation)
    - Shadow Adapter (I/O persistence)

    Invariant: Orchestration only, no business logic.
    """

    def __init__(
        self,
        shadow_adapter: ShadowAdapter,
        default_config: Optional[SimulationConfig] = None,
    ):
        """Initialize Phantom orchestrator.

        Args:
            shadow_adapter: Shadow persistence adapter
            default_config: Default simulation configuration
        """
        self.adapter = shadow_adapter
        self.kernel: PhantomKernel = None  # Will be injected
        self.default_config = default_config or SimulationConfig(
            max_states=10000,
            max_depth=100,
        )

    def set_kernel(self, kernel: PhantomKernel) -> None:
        """Inject Phantom kernel implementation.

        Args:
            kernel: Phantom kernel instance
        """
        self.kernel = kernel

    async def simulate_from_shadow(
        self,
        file_path: str,
        config: Optional[SimulationConfig] = None,
    ) -> Tuple[PhantomResult, ...]:
        """Load shadow file and run Monte Carlo simulation.

        Args:
            file_path: Path to shadow file (relative to shadows directory)
            config: Simulation configuration (defaults to orchestrator config)

        Returns:
            Tuple of PhantomResult objects

        Pipeline:
            1. Load shadow file (adapter)
            2. Parse atoms into thread sequences
            3. Run simulation (kernel)
        """
        if self.kernel is None:
            raise RuntimeError("Phantom kernel not injected")

        # Step 1: Load shadow file (I/O)
        request = ShadowReadRequest(file_path=file_path)
        shadow = await self.adapter.read_shadow(request)
        if shadow is None:
            return ()

        # Step 2: Parse atoms into thread sequences
        threads = self._parse_threads(shadow)

        # Step 3: Run simulation (pure computation)
        config = config or self.default_config
        results = self.kernel.simulate(threads, config)

        return tuple(results)

    async def simulate_and_store(
        self,
        file_path: str,
        atoms: Tuple[Atom, ...],
        config: Optional[SimulationConfig] = None,
    ) -> Tuple[PhantomResult, ...]:
        """Run simulation on atoms and store shadow file.

        Args:
            file_path: Path to shadow file (relative to shadows directory)
            atoms: Atom sequence to simulate
            config: Simulation configuration

        Returns:
            Tuple of PhantomResult objects

        Pipeline:
            1. Convert atoms to thread sequences
            2. Run simulation (kernel)
            3. Store shadow file (adapter)
        """
        if self.kernel is None:
            raise RuntimeError("Phantom kernel not injected")

        # Step 1: Convert atoms to thread sequences
        threads = [ThreadSequence(symbol_name="test", atoms=atoms)]

        # Step 2: Run simulation (pure computation)
        config = config or self.default_config
        results = self.kernel.simulate(threads, config)

        # Step 3: Store shadow file (I/O)
        shadow = ShadowFile(
            symbol="test",
            deps=(),
            checksum="",
            atoms=tuple(DSLAtom(op=a.op, resource=a.arg, line_hint=a.line) for a in atoms),
        )
        write_request = ShadowWriteRequest(
            file_path=file_path,
            shadow=shadow,
        )
        await self.adapter.write_shadow(write_request)

        return tuple(results)

    async def validate_shadow(
        self,
        file_path: str,
        config: Optional[SimulationConfig] = None,
    ) -> bool:
        """Validate shadow file has no deadlocks.

        Args:
            file_path: Path to shadow file
            config: Simulation configuration

        Returns:
            True if no deadlocks found, False otherwise

        Pipeline:
            1. Load shadow file (adapter)
            2. Run simulation (kernel)
            3. Check for deadlock verdicts
        """
        results = await self.simulate_from_shadow(file_path, config)

        # Check if any result has deadlock verdict
        for result in results:
            if result.verdict in ("DEADLOCK_RISK", "RESOURCE_LEAK"):
                return False

        return True

    async def get_shadow_checksum(
        self,
        file_path: str,
    ) -> Optional[str]:
        """Get checksum of shadow file.

        Args:
            file_path: Path to shadow file

        Returns:
            Checksum string if file exists, None otherwise

        Pipeline:
            1. Load shadow file (adapter)
            2. Return checksum
        """
        request = ShadowReadRequest(file_path=file_path)
        shadow = await self.adapter.read_shadow(request)
        if shadow is None:
            return None

        return shadow.checksum

    async def list_all_shadows(self) -> Tuple[str, ...]:
        """List all shadow files.

        Returns:
            Tuple of shadow file paths

        Pipeline:
            1. List shadows (adapter)
        """
        shadows = await self.adapter.list_shadows()
        return shadows

    def _parse_threads(self, shadow: ShadowFile) -> List[ThreadSequence]:
        """Parse shadow file atoms into thread sequences.

        Args:
            shadow: Shadow file

        Returns:
            List of ThreadSequence objects

        Note: Current implementation assumes single-threaded.
        Multi-threaded parsing would split atoms by thread boundaries.
        """
        # Convert DSLAtom to Atom
        atoms = tuple(
            Atom(op=a.op, arg=a.resource, line=a.line_hint)
            for a in shadow.atoms
        )
        # For now, treat all atoms as single thread
        return [ThreadSequence(symbol_name=shadow.symbol, atoms=atoms)]
