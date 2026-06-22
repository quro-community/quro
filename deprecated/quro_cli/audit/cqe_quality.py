"""
CQE index quality auditor.

Audits CQE SQLite index for:
- Atom completeness and distribution
- Morphism connectivity and quality
- MI score coverage
- Index integrity
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import Counter


@dataclass
class CQEQualityReport:
    """CQE index quality audit report"""

    # Atom metrics
    total_atoms: int
    atom_types: Dict[str, int]
    symbols_with_features: int
    symbols_with_minhash: int
    symbols_with_topk_tokens: int

    # Morphism metrics
    total_morphisms: int
    morphism_kinds: Dict[str, int]
    avg_morphisms_per_atom: float
    atoms_with_no_morphisms: int
    max_morphisms_per_atom: int
    min_morphisms_per_atom: int

    # Connectivity metrics
    connected_components: int
    largest_component_size: int
    avg_component_size: float
    isolated_atoms_pct: float

    # MI score metrics
    mi_scores_count: int
    mi_coverage_pct: float
    avg_mi_score: Optional[float]

    # Quality gates
    quality_grade: str  # A, B, C, D, F
    ready_for_queries: bool
    issues: List[str]
    recommendations: List[str]


class CQEQualityAuditor:
    """Audit CQE index quality"""

    def __init__(self, index_path: Path):
        self.index_path = index_path
        self.conn: Optional[sqlite3.Connection] = None

    def setup(self):
        """Open database connection"""
        if not self.index_path.exists():
            raise FileNotFoundError(f"CQE index not found: {self.index_path}")
        self.conn = sqlite3.connect(str(self.index_path))
        self.conn.row_factory = sqlite3.Row

    def cleanup(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def audit(self) -> CQEQualityReport:
        """Run full CQE quality audit"""
        if not self.conn:
            self.setup()

        cursor = self.conn.cursor()

        # Atom metrics
        total_atoms = cursor.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]

        atom_types = {}
        for row in cursor.execute("SELECT type, COUNT(*) as count FROM atoms GROUP BY type"):
            atom_types[row['type']] = row['count']

        symbols_with_features = cursor.execute(
            "SELECT COUNT(*) FROM atoms WHERE type = 'symbol' AND features_json IS NOT NULL"
        ).fetchone()[0]

        symbols_with_minhash = cursor.execute(
            "SELECT COUNT(*) FROM atoms WHERE type = 'symbol' AND minhash_blob IS NOT NULL"
        ).fetchone()[0]

        symbols_with_topk = cursor.execute(
            "SELECT COUNT(*) FROM atoms WHERE type = 'symbol' AND topk_tokens_json IS NOT NULL"
        ).fetchone()[0]

        # Morphism metrics
        total_morphisms = cursor.execute("SELECT COUNT(*) FROM morphisms").fetchone()[0]

        morphism_kinds = {}
        for row in cursor.execute("SELECT kind, COUNT(*) as count FROM morphisms GROUP BY kind"):
            morphism_kinds[row['kind']] = row['count']

        avg_morphisms = (total_morphisms / total_atoms) if total_atoms > 0 else 0

        # Morphisms per atom distribution
        morphism_dist = cursor.execute("""
            SELECT
                atom_id,
                COUNT(*) as morphism_count
            FROM (
                SELECT from_id as atom_id FROM morphisms
                UNION ALL
                SELECT to_id as atom_id FROM morphisms
            )
            GROUP BY atom_id
        """).fetchall()

        if morphism_dist:
            morphism_counts = [row['morphism_count'] for row in morphism_dist]
            max_morphisms = max(morphism_counts)
            min_morphisms = min(morphism_counts)
        else:
            max_morphisms = 0
            min_morphisms = 0

        atoms_with_morphisms = len(morphism_dist)
        atoms_no_morphisms = total_atoms - atoms_with_morphisms
        isolated_pct = (atoms_no_morphisms / total_atoms * 100) if total_atoms > 0 else 0

        # Connectivity analysis (simplified - just count isolated vs connected)
        connected_atoms = atoms_with_morphisms
        isolated_atoms = atoms_no_morphisms

        # Estimate connected components (simplified)
        if connected_atoms > 0:
            # Rough estimate: assume most connected atoms are in one large component
            connected_components = 1 + isolated_atoms
            largest_component_size = connected_atoms
            avg_component_size = connected_atoms / 1 if connected_atoms > 0 else 0
        else:
            connected_components = isolated_atoms
            largest_component_size = 1
            avg_component_size = 1

        # MI score metrics
        mi_scores_count = 0
        avg_mi_score = None
        try:
            mi_scores_count = cursor.execute("SELECT COUNT(*) FROM mi_scores").fetchone()[0]
            if mi_scores_count > 0:
                avg_mi_score = cursor.execute("SELECT AVG(mi_score) FROM mi_scores").fetchone()[0]
        except sqlite3.OperationalError:
            # mi_scores table might not exist yet
            pass

        # MI coverage (percentage of atom pairs with MI scores)
        max_possible_pairs = total_atoms * (total_atoms - 1) / 2
        mi_coverage_pct = (mi_scores_count / max_possible_pairs * 100) if max_possible_pairs > 0 else 0

        # Quality assessment
        issues = []
        recommendations = []

        # Check atom completeness
        symbol_count = atom_types.get('symbol', 0)
        if symbol_count == 0:
            issues.append("No symbol atoms found in index")
            recommendations.append("Rebuild CQE index from database")

        # Check feature completeness
        if symbol_count > 0:
            feature_pct = (symbols_with_features / symbol_count * 100)
            if feature_pct < 90:
                issues.append(f"Only {feature_pct:.1f}% of symbols have features (target: >90%)")
                recommendations.append("Ensure semantic scan completes before building index")

            minhash_pct = (symbols_with_minhash / symbol_count * 100)
            if minhash_pct < 80:
                issues.append(f"Only {minhash_pct:.1f}% of symbols have MinHash (target: >80%)")
                recommendations.append("Run LSH engine to generate MinHash signatures")

        # Check morphism connectivity
        if avg_morphisms < 5:
            issues.append(f"Average morphisms per atom is {avg_morphisms:.2f} (target: >5)")
            recommendations.append("Add more morphism types or improve edge quality")

        # Check isolated atoms
        if isolated_pct > 15:
            issues.append(f"{isolated_pct:.1f}% of atoms are isolated (target: <15%)")
            recommendations.append("Investigate why atoms have no connections")

        # Check MI scores
        if mi_scores_count == 0:
            issues.append("No MI scores found - MI Estimator not yet implemented")
            recommendations.append("Implement MI Estimator after data quality is sufficient")

        # Determine quality grade
        # Grade A: High structural connectivity + complete features + low isolation
        # Grade B: Good connectivity + solid features
        # Grade C: Adequate but needs improvement
        # Grade D: Below minimum thresholds
        # Grade F: Critical issues

        # Compute structural edge ratio (CALLS + DEFINES vs total)
        structural_morphisms = morphism_kinds.get('CALLS', 0) + morphism_kinds.get('DEFINES', 0)
        structural_ratio = structural_morphisms / total_morphisms if total_morphisms > 0 else 0

        if (avg_morphisms >= 10 and isolated_pct < 10 and
            feature_pct >= 95 and minhash_pct >= 90):
            quality_grade = 'A'
        elif (avg_morphisms >= 5 and isolated_pct < 15 and
              feature_pct >= 90 and minhash_pct >= 80 and
              structural_ratio >= 0.05):
            quality_grade = 'A-'
        elif (avg_morphisms >= 5 and isolated_pct < 15 and
              feature_pct >= 90 and minhash_pct >= 80):
            quality_grade = 'B'
        elif (avg_morphisms >= 3 and isolated_pct < 20 and
              feature_pct >= 80 and minhash_pct >= 70):
            quality_grade = 'C'
        elif avg_morphisms >= 1 and isolated_pct < 30:
            quality_grade = 'D'
        else:
            quality_grade = 'F'

        # Ready for queries?
        ready_for_queries = (
            avg_morphisms >= 5 and
            isolated_pct < 20 and
            symbol_count > 0 and
            feature_pct >= 80
        )

        if not ready_for_queries:
            recommendations.append("Improve index quality before running production queries")

        return CQEQualityReport(
            total_atoms=total_atoms,
            atom_types=atom_types,
            symbols_with_features=symbols_with_features,
            symbols_with_minhash=symbols_with_minhash,
            symbols_with_topk_tokens=symbols_with_topk,
            total_morphisms=total_morphisms,
            morphism_kinds=morphism_kinds,
            avg_morphisms_per_atom=round(avg_morphisms, 2),
            atoms_with_no_morphisms=atoms_no_morphisms,
            max_morphisms_per_atom=max_morphisms,
            min_morphisms_per_atom=min_morphisms,
            connected_components=connected_components,
            largest_component_size=largest_component_size,
            avg_component_size=round(avg_component_size, 2),
            isolated_atoms_pct=round(isolated_pct, 1),
            mi_scores_count=mi_scores_count,
            mi_coverage_pct=round(mi_coverage_pct, 4),
            avg_mi_score=round(avg_mi_score, 4) if avg_mi_score else None,
            quality_grade=quality_grade,
            ready_for_queries=ready_for_queries,
            issues=issues,
            recommendations=recommendations
        )

    def print_report(self, report: CQEQualityReport):
        """Print formatted audit report"""
        print("\n" + "="*80)
        print("CQE INDEX QUALITY AUDIT REPORT")
        print("="*80)

        print(f"\n📊 Atom Metrics:")
        print(f"  Total Atoms: {report.total_atoms:,}")
        print(f"  Atom Types:")
        for atype, count in report.atom_types.items():
            print(f"    {atype:12s}: {count:,}")

        symbol_count = report.atom_types.get('symbol', 0)
        if symbol_count > 0:
            print(f"\n  Symbol Completeness:")
            print(f"    With Features:    {report.symbols_with_features:,} ({report.symbols_with_features/symbol_count*100:.1f}%)")
            print(f"    With MinHash:     {report.symbols_with_minhash:,} ({report.symbols_with_minhash/symbol_count*100:.1f}%)")
            print(f"    With TopK Tokens: {report.symbols_with_topk_tokens:,} ({report.symbols_with_topk_tokens/symbol_count*100:.1f}%)")

        print(f"\n🔗 Morphism Metrics:")
        print(f"  Total Morphisms: {report.total_morphisms:,}")
        print(f"  Morphism Kinds:")
        for kind, count in report.morphism_kinds.items():
            print(f"    {kind:12s}: {count:,}")
        print(f"  Avg per Atom:    {report.avg_morphisms_per_atom:.2f}")
        print(f"  Max per Atom:    {report.max_morphisms_per_atom:,}")
        print(f"  Min per Atom:    {report.min_morphisms_per_atom:,}")
        print(f"  Isolated Atoms:  {report.atoms_with_no_morphisms:,} ({report.isolated_atoms_pct}%)")
        status = "✅" if report.avg_morphisms_per_atom >= 5 else "⚠️"
        print(f"  Status:          {status} {'GOOD' if report.avg_morphisms_per_atom >= 5 else 'NEEDS IMPROVEMENT'}")

        print(f"\n🌐 Connectivity:")
        print(f"  Connected Components:   {report.connected_components:,}")
        print(f"  Largest Component:      {report.largest_component_size:,}")
        print(f"  Avg Component Size:     {report.avg_component_size:.2f}")
        print(f"  Isolated Atoms:         {report.isolated_atoms_pct}%")
        status = "✅" if report.isolated_atoms_pct < 15 else "⚠️"
        print(f"  Status:                 {status} {'GOOD' if report.isolated_atoms_pct < 15 else 'NEEDS IMPROVEMENT'}")

        print(f"\n🧠 MI Score Metrics:")
        print(f"  MI Scores Count:  {report.mi_scores_count:,}")
        print(f"  MI Coverage:      {report.mi_coverage_pct:.4f}%")
        if report.avg_mi_score is not None:
            print(f"  Avg MI Score:     {report.avg_mi_score:.4f}")
        else:
            print(f"  Avg MI Score:     N/A (no scores yet)")
        status = "✅" if report.mi_scores_count > 0 else "⚠️"
        print(f"  Status:           {status} {'IMPLEMENTED' if report.mi_scores_count > 0 else 'NOT YET IMPLEMENTED'}")

        print(f"\n📈 Quality Grade: {report.quality_grade}")

        if report.issues:
            print(f"\n⚠️  Issues Found:")
            for issue in report.issues:
                print(f"  - {issue}")

        if report.recommendations:
            print(f"\n💡 Recommendations:")
            for rec in report.recommendations:
                print(f"  - {rec}")

        print(f"\n🎯 Ready for Production Queries: {'✅ YES' if report.ready_for_queries else '❌ NO'}")

        print("\n" + "="*80 + "\n")

    def save_report(self, report: CQEQualityReport, output_path: Path):
        """Save report to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"Report saved to: {output_path}")


def main():
    """CLI entry point"""
    import sys

    index_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".quro_context/cqe_index.db")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".quro_context/audit/cqe_quality_report.json")

    auditor = CQEQualityAuditor(index_path)
    try:
        report = auditor.audit()
        auditor.print_report(report)
        auditor.save_report(report, output_path)
    finally:
        auditor.cleanup()


if __name__ == "__main__":
    main()
