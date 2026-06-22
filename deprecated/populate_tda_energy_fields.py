#!/usr/bin/env python3
"""Populate TDA Energy Fields with Laplace Smoothing

Fixes the "Absolute Zero Sink" issue where all energy fields are 0.0.
Implements baseline energy computation based on topology and cognitive mass.

Usage:
    python scripts/populate_tda_energy_fields.py
"""

import sqlite3
import math
from pathlib import Path


class EnergyFieldPopulator:
    """Populate energy fields in tda_manifold_states table."""

    # Laplace smoothing parameters
    MIN_ENERGY_BASELINE = 0.1  # Minimum energy for any node with mass > 0
    ENERGY_SCALE_FACTOR = 0.5  # Scale factor for mass-based energy

    def __init__(self, tda_db_path: Path):
        self.tda_db_path = tda_db_path
        self._conn = None

    def __enter__(self):
        self._conn = sqlite3.connect(str(self.tda_db_path))
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()

    def populate(self):
        """Populate energy fields with Laplace-smoothed baseline values."""
        print("=" * 80)
        print("POPULATING TDA ENERGY FIELDS")
        print("=" * 80)
        print(f"Database: {self.tda_db_path}")
        print()

        # Get all symbols
        cursor = self._conn.execute("""
            SELECT symbol, cognitive_mass, gravity, centrality, betweenness
            FROM tda_manifold_states
        """)

        symbols = cursor.fetchall()
        print(f"Processing {len(symbols)} symbols...")
        print()

        updated = 0
        for row in symbols:
            symbol = row["symbol"]
            cognitive_mass = row["cognitive_mass"]
            gravity = row["gravity"]
            centrality = row["centrality"]
            betweenness = row["betweenness"]

            # Compute energy fields with Laplace smoothing
            energy_fields = self._compute_energy_fields(
                cognitive_mass, gravity, centrality, betweenness
            )

            # Update database
            self._conn.execute("""
                UPDATE tda_manifold_states
                SET
                    field_magnitude = ?,
                    energy_potential = ?,
                    energy_kinetic = ?,
                    energy_total = ?
                WHERE symbol = ?
            """, (
                energy_fields["field_magnitude"],
                energy_fields["energy_potential"],
                energy_fields["energy_kinetic"],
                energy_fields["energy_total"],
                symbol,
            ))

            updated += 1
            if updated % 500 == 0:
                print(f"  Updated {updated}/{len(symbols)} symbols ({100*updated/len(symbols):.1f}%)...")
                self._conn.commit()

        self._conn.commit()

        print()
        print(f"✓ Updated {updated} symbols with energy fields")
        print()

        # Print statistics
        self._print_statistics()

    def _compute_energy_fields(
        self,
        cognitive_mass: float,
        gravity: float,
        centrality: float,
        betweenness: float
    ) -> dict:
        """Compute energy fields with Laplace smoothing.

        Formula:
        - energy_potential = max(MIN_BASELINE, mass * gravity * SCALE)
        - energy_kinetic = max(MIN_BASELINE, mass * centrality * SCALE)
        - energy_total = potential + kinetic
        - field_magnitude = sqrt(total_energy)

        This ensures:
        1. No absolute zeros (all nodes have MIN_BASELINE energy)
        2. Energy scales with cognitive mass
        3. Gravity affects potential energy
        4. Centrality affects kinetic energy
        5. Gradients exist for navigation

        Args:
            cognitive_mass: Node cognitive mass
            gravity: Gravity score [0, 1]
            centrality: Centrality score [0, 1]
            betweenness: Betweenness score [0, 1]

        Returns:
            Dict with field_magnitude, energy_potential, energy_kinetic, energy_total
        """
        # Potential energy: mass × gravity (position in field)
        energy_potential = max(
            self.MIN_ENERGY_BASELINE,
            cognitive_mass * gravity * self.ENERGY_SCALE_FACTOR
        )

        # Kinetic energy: mass × centrality (flow through node)
        # Use betweenness as a secondary factor
        flow_factor = (centrality + betweenness) / 2.0
        energy_kinetic = max(
            self.MIN_ENERGY_BASELINE,
            cognitive_mass * flow_factor * self.ENERGY_SCALE_FACTOR
        )

        # Total energy
        energy_total = energy_potential + energy_kinetic

        # Field magnitude: sqrt of total energy (field strength)
        field_magnitude = math.sqrt(energy_total)

        return {
            "field_magnitude": field_magnitude,
            "energy_potential": energy_potential,
            "energy_kinetic": energy_kinetic,
            "energy_total": energy_total,
        }

    def _print_statistics(self):
        """Print energy field statistics."""
        print("=" * 80)
        print("ENERGY FIELD STATISTICS")
        print("=" * 80)

        # Count non-zero energy nodes
        cursor = self._conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN energy_total > 0.0 THEN 1 ELSE 0 END) as nonzero,
                AVG(energy_total) as avg_energy,
                MIN(energy_total) as min_energy,
                MAX(energy_total) as max_energy,
                AVG(field_magnitude) as avg_field
            FROM tda_manifold_states
        """)

        row = cursor.fetchone()

        print(f"Total symbols: {row['total']:,}")
        print(f"Non-zero energy: {row['nonzero']:,} ({100*row['nonzero']/row['total']:.1f}%)")
        print(f"Average energy: {row['avg_energy']:.4f}")
        print(f"Min energy: {row['min_energy']:.4f}")
        print(f"Max energy: {row['max_energy']:.4f}")
        print(f"Average field magnitude: {row['avg_field']:.4f}")
        print()

        # Energy distribution
        cursor = self._conn.execute("""
            SELECT
                CASE
                    WHEN energy_total = 0.0 THEN 'Zero'
                    WHEN energy_total < 0.5 THEN 'Low (< 0.5)'
                    WHEN energy_total < 2.0 THEN 'Medium (0.5-2.0)'
                    WHEN energy_total < 5.0 THEN 'High (2.0-5.0)'
                    ELSE 'Very High (> 5.0)'
                END as energy_range,
                COUNT(*) as count
            FROM tda_manifold_states
            GROUP BY energy_range
            ORDER BY MIN(energy_total)
        """)

        print("Energy Distribution:")
        for row in cursor:
            print(f"  {row['energy_range']}: {row['count']:,}")
        print()

        print("=" * 80)


def main():
    """CLI entry point."""
    workspace_root = Path.cwd()
    tda_db_path = workspace_root / ".quro_context" / "tda_index.db"

    if not tda_db_path.exists():
        print(f"Error: TDA index not found: {tda_db_path}")
        print("Run migration script first: python scripts/migrate_tda_schema.py")
        return 1

    with EnergyFieldPopulator(tda_db_path) as populator:
        populator.populate()

    print("✅ Energy field population complete!")
    print()
    print("Next steps:")
    print("  1. Rebuild CQE index to pick up new energy values")
    print("  2. Test TDA navigation - should now have gradients")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
