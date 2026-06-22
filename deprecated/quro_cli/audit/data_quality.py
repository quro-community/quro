"""
Database data quality auditor.

Audits PostgreSQL database for:
- Symbol completeness (scan_completed rate)
- Semantic data quality (role, intent, tags)
- Morphism edge quality (coverage, weights)
- File coverage and language distribution
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncpg
from dataclasses import dataclass, asdict


@dataclass
class DataQualityReport:
    """Data quality audit report"""

    # Overall metrics
    total_symbols: int
    total_files: int
    total_morphisms: int

    # Scan completeness
    scan_completed_count: int
    scan_completed_pct: float
    scan_pending_count: int

    # Semantic data quality
    symbols_with_role: int
    symbols_with_intent: int
    symbols_with_tags: int
    semantic_completeness_pct: float

    # Morphism quality
    morphism_types: Dict[str, int]
    avg_morphisms_per_symbol: float
    symbols_with_no_morphisms: int

    # Language distribution
    language_distribution: Dict[str, Dict[str, Any]]

    # Quality gates
    quality_grade: str  # A, B, C, D, F
    ready_for_mi_estimator: bool
    issues: List[str]
    recommendations: List[str]


class DatabaseQualityAuditor:
    """Audit database data quality"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def setup(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=5)

    async def cleanup(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()

    async def audit(self) -> DataQualityReport:
        """Run full data quality audit"""
        if not self.pool:
            await self.setup()

        async with self.pool.acquire() as conn:
            # Overall metrics
            self.pool.release()
            total_symbols = await conn.fetchval("SELECT COUNT(*) FROM symbols")
            total_files = await conn.fetchval("SELECT COUNT(*) FROM files")
            total_morphisms = await conn.fetchval("SELECT COUNT(*) FROM morphism_edges")

            # Scan completeness
            scan_completed = await conn.fetchval(
                "SELECT COUNT(*) FROM symbols WHERE scan_completed = TRUE"
            )
            scan_pending = total_symbols - scan_completed
            scan_pct = (scan_completed / total_symbols * 100) if total_symbols > 0 else 0

            # Semantic data quality
            symbols_with_role = await conn.fetchval(
                "SELECT COUNT(*) FROM symbols WHERE role IS NOT NULL AND role != ''"
            )
            symbols_with_intent = await conn.fetchval(
                "SELECT COUNT(*) FROM symbols WHERE intent IS NOT NULL AND intent != ''"
            )
            symbols_with_tags = await conn.fetchval(
                "SELECT COUNT(*) FROM symbols WHERE tags IS NOT NULL AND tags::text != '[]'"
            )

            # Semantic completeness (average of role, intent, tags)
            semantic_completeness = (
                (symbols_with_role + symbols_with_intent + symbols_with_tags)
                / (total_symbols * 3) * 100
            ) if total_symbols > 0 else 0

            # Morphism quality
            morphism_types = {}
            rows = await conn.fetch("""
                SELECT mt.type_name, COUNT(*) as count
                FROM morphism_edges me
                JOIN morphism_types mt ON me.morphism_type_id = mt.id
                GROUP BY mt.type_name
                ORDER BY count DESC
            """)
            for row in rows:
                morphism_types[row['type_name']] = row['count']

            avg_morphisms = (total_morphisms / total_symbols) if total_symbols > 0 else 0

            # Symbols with no morphisms
            symbols_no_morphisms = await conn.fetchval("""
                SELECT COUNT(*) FROM symbols s
                WHERE NOT EXISTS (
                    SELECT 1 FROM morphism_edges me
                    WHERE me.from_symbol_id = s.id OR me.to_symbol_id = s.id
                )
            """)

            # Language distribution
            lang_rows = await conn.fetch("""
                SELECT
                    f.language,
                    COUNT(s.id) as symbol_count,
                    COUNT(*) FILTER (WHERE s.scan_completed = TRUE) as completed,
                    COUNT(*) FILTER (WHERE s.role IS NOT NULL) as with_role,
                    COUNT(*) FILTER (WHERE s.intent IS NOT NULL) as with_intent,
                    COUNT(*) FILTER (WHERE s.tags IS NOT NULL AND s.tags::text != '[]') as with_tags
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                GROUP BY f.language
                ORDER BY symbol_count DESC
            """)

            language_distribution = {}
            for row in lang_rows:
                lang = row['language']
                symbol_count = row['symbol_count']
                language_distribution[lang] = {
                    'symbol_count': symbol_count,
                    'completed': row['completed'],
                    'completed_pct': round(row['completed'] / symbol_count * 100, 1) if symbol_count > 0 else 0,
                    'with_role': row['with_role'],
                    'with_intent': row['with_intent'],
                    'with_tags': row['with_tags'],
                    'semantic_pct': round(
                        (row['with_role'] + row['with_intent'] + row['with_tags'])
                        / (symbol_count * 3) * 100, 1
                    ) if symbol_count > 0 else 0
                }

        # Quality assessment
        issues = []
        recommendations = []

        # Check scan completeness
        if scan_pct < 80:
            issues.append(f"Scan completeness is {scan_pct:.1f}% (target: >80%)")
            recommendations.append("Run semantic scan to completion before proceeding")

        # Check semantic data quality
        if semantic_completeness < 60:
            issues.append(f"Semantic completeness is {semantic_completeness:.1f}% (target: >60%)")
            recommendations.append("Improve semantic data extraction (role, intent, tags)")

        # Check morphism connectivity
        if avg_morphisms < 5:
            issues.append(f"Average morphisms per symbol is {avg_morphisms:.1f} (target: >5)")
            recommendations.append("Add more morphism types or improve edge creation")

        # Check isolated symbols
        isolated_pct = (symbols_no_morphisms / total_symbols * 100) if total_symbols > 0 else 0
        if isolated_pct > 10:
            issues.append(f"{isolated_pct:.1f}% of symbols have no morphisms (target: <10%)")
            recommendations.append("Investigate why symbols are isolated from the graph")

        # Determine quality grade
        if scan_pct >= 95 and semantic_completeness >= 80 and avg_morphisms >= 10:
            quality_grade = 'A'
        elif scan_pct >= 90 and semantic_completeness >= 70 and avg_morphisms >= 5:
            quality_grade = 'B'
        elif scan_pct >= 80 and semantic_completeness >= 60 and avg_morphisms >= 3:
            quality_grade = 'C'
        elif scan_pct >= 70 and semantic_completeness >= 50 and avg_morphisms >= 1:
            quality_grade = 'D'
        else:
            quality_grade = 'F'

        # Ready for MI Estimator?
        ready_for_mi = (
            scan_pct >= 80 and
            semantic_completeness >= 60 and
            avg_morphisms >= 5 and
            isolated_pct < 15
        )

        if not ready_for_mi:
            recommendations.append("Complete data quality improvements before implementing MI Estimator")

        return DataQualityReport(
            total_symbols=total_symbols,
            total_files=total_files,
            total_morphisms=total_morphisms,
            scan_completed_count=scan_completed,
            scan_completed_pct=round(scan_pct, 1),
            scan_pending_count=scan_pending,
            symbols_with_role=symbols_with_role,
            symbols_with_intent=symbols_with_intent,
            symbols_with_tags=symbols_with_tags,
            semantic_completeness_pct=round(semantic_completeness, 1),
            morphism_types=morphism_types,
            avg_morphisms_per_symbol=round(avg_morphisms, 2),
            symbols_with_no_morphisms=symbols_no_morphisms,
            language_distribution=language_distribution,
            quality_grade=quality_grade,
            ready_for_mi_estimator=ready_for_mi,
            issues=issues,
            recommendations=recommendations
        )

    def print_report(self, report: DataQualityReport):
        """Print formatted audit report"""
        print("\n" + "="*80)
        print("DATABASE DATA QUALITY AUDIT REPORT")
        print("="*80)

        print(f"\n📊 Overall Metrics:")
        print(f"  Total Symbols:   {report.total_symbols:,}")
        print(f"  Total Files:     {report.total_files:,}")
        print(f"  Total Morphisms: {report.total_morphisms:,}")

        print(f"\n🔍 Scan Completeness:")
        print(f"  Completed: {report.scan_completed_count:,} ({report.scan_completed_pct}%)")
        print(f"  Pending:   {report.scan_pending_count:,} ({100 - report.scan_completed_pct:.1f}%)")
        status = "✅" if report.scan_completed_pct >= 80 else "⚠️"
        print(f"  Status:    {status} {'GOOD' if report.scan_completed_pct >= 80 else 'NEEDS IMPROVEMENT'}")

        print(f"\n🧠 Semantic Data Quality:")
        print(f"  With Role:   {report.symbols_with_role:,} ({report.symbols_with_role/report.total_symbols*100:.1f}%)")
        print(f"  With Intent: {report.symbols_with_intent:,} ({report.symbols_with_intent/report.total_symbols*100:.1f}%)")
        print(f"  With Tags:   {report.symbols_with_tags:,} ({report.symbols_with_tags/report.total_symbols*100:.1f}%)")
        print(f"  Overall:     {report.semantic_completeness_pct}%")
        status = "✅" if report.semantic_completeness_pct >= 60 else "⚠️"
        print(f"  Status:      {status} {'GOOD' if report.semantic_completeness_pct >= 60 else 'NEEDS IMPROVEMENT'}")

        print(f"\n🔗 Morphism Quality:")
        print(f"  Morphism Types:")
        for mtype, count in report.morphism_types.items():
            print(f"    {mtype:12s}: {count:,}")
        print(f"  Avg per Symbol:  {report.avg_morphisms_per_symbol:.2f}")
        print(f"  Isolated:        {report.symbols_with_no_morphisms:,} ({report.symbols_with_no_morphisms/report.total_symbols*100:.1f}%)")
        status = "✅" if report.avg_morphisms_per_symbol >= 5 else "⚠️"
        print(f"  Status:          {status} {'GOOD' if report.avg_morphisms_per_symbol >= 5 else 'NEEDS IMPROVEMENT'}")

        print(f"\n🌐 Language Distribution:")
        for lang, stats in report.language_distribution.items():
            print(f"  {lang}:")
            print(f"    Symbols:  {stats['symbol_count']:,}")
            print(f"    Scanned:  {stats['completed']:,} ({stats['completed_pct']}%)")
            print(f"    Semantic: {stats['semantic_pct']}%")

        print(f"\n📈 Quality Grade: {report.quality_grade}")

        if report.issues:
            print(f"\n⚠️  Issues Found:")
            for issue in report.issues:
                print(f"  - {issue}")

        if report.recommendations:
            print(f"\n💡 Recommendations:")
            for rec in report.recommendations:
                print(f"  - {rec}")

        print(f"\n🎯 Ready for MI Estimator: {'✅ YES' if report.ready_for_mi_estimator else '❌ NO'}")

        print("\n" + "="*80 + "\n")

    async def save_report(self, report: DataQualityReport, output_path: Path):
        """Save report to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"Report saved to: {output_path}")


async def main():
    """CLI entry point"""
    import sys

    db_url = sys.argv[1] if len(sys.argv) > 1 else "postgresql://localhost/quro_db"
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".quro_context/audit/data_quality_report.json")

    auditor = DatabaseQualityAuditor(db_url)
    try:
        report = await auditor.audit()
        auditor.print_report(report)
        await auditor.save_report(report, output_path)
    finally:
        await auditor.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
