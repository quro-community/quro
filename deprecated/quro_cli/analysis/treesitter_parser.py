"""
Tree-sitter Parser

Provides fallback parsing for TypeScript and JavaScript using tree-sitter.
Used when TypeScript probe is unavailable.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TreeSitterSymbol:
    """Tree-sitter symbol information"""
    name: str
    kind: str  # function, class, variable, method, interface
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass
class TreeSitterImport:
    """Tree-sitter import information"""
    source: str
    names: List[str]
    line: int


class TreeSitterParser:
    """
    Tree-sitter parser for TypeScript and JavaScript

    Note: This is a placeholder implementation.
    Full tree-sitter integration requires:
    - pip install tree-sitter tree-sitter-typescript tree-sitter-javascript
    - Building language binaries

    For now, provides basic regex-based fallback.
    """

    def __init__(self):
        """Initialize tree-sitter parser"""
        self.ts_available = False
        try:
            import tree_sitter
            self.ts_available = True
        except ImportError:
            # Tree-sitter not available, use regex fallback
            pass

    def parse_typescript(self, file_path: str) -> Optional[Any]:
        """
        Parse TypeScript file

        Args:
            file_path: Path to TypeScript file

        Returns:
            Parse tree or None
        """
        if not self.ts_available:
            return None

        # TODO: Implement actual tree-sitter parsing
        # For now, return None to trigger fallback
        return None

    def parse_javascript(self, file_path: str) -> Optional[Any]:
        """
        Parse JavaScript file

        Args:
            file_path: Path to JavaScript file

        Returns:
            Parse tree or None
        """
        if not self.ts_available:
            return None

        # TODO: Implement actual tree-sitter parsing
        return None

    def extract_symbols(self, tree: Any, source: str) -> List[TreeSitterSymbol]:
        """
        Extract symbols from parse tree

        Args:
            tree: Parse tree
            source: Source code

        Returns:
            List of symbols
        """
        if not tree:
            return self._extract_symbols_regex(source)

        # TODO: Implement actual tree-sitter symbol extraction
        return []

    def extract_imports(self, tree: Any, source: str) -> List[TreeSitterImport]:
        """
        Extract imports from parse tree

        Args:
            tree: Parse tree
            source: Source code

        Returns:
            List of imports
        """
        if not tree:
            return self._extract_imports_regex(source)

        # TODO: Implement actual tree-sitter import extraction
        return []

    def _extract_symbols_regex(self, source: str) -> List[TreeSitterSymbol]:
        """
        Fallback: Extract symbols using regex

        Args:
            source: Source code

        Returns:
            List of symbols
        """
        import re
        symbols = []

        # Match function declarations
        # function foo() { ... }
        # async function foo() { ... }
        func_pattern = r'(?:async\s+)?function\s+(\w+)\s*\('
        for match in re.finditer(func_pattern, source):
            line = source[:match.start()].count('\n') + 1
            col = match.start() - source[:match.start()].rfind('\n') - 1
            symbols.append(TreeSitterSymbol(
                name=match.group(1),
                kind="function",
                line=line,
                col=col,
                end_line=line,
                end_col=col + len(match.group(0))
            ))

        # Match class declarations
        # class Foo { ... }
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, source):
            line = source[:match.start()].count('\n') + 1
            col = match.start() - source[:match.start()].rfind('\n') - 1
            symbols.append(TreeSitterSymbol(
                name=match.group(1),
                kind="class",
                line=line,
                col=col,
                end_line=line,
                end_col=col + len(match.group(0))
            ))

        # Match interface declarations (TypeScript)
        # interface Foo { ... }
        interface_pattern = r'interface\s+(\w+)'
        for match in re.finditer(interface_pattern, source):
            line = source[:match.start()].count('\n') + 1
            col = match.start() - source[:match.start()].rfind('\n') - 1
            symbols.append(TreeSitterSymbol(
                name=match.group(1),
                kind="interface",
                line=line,
                col=col,
                end_line=line,
                end_col=col + len(match.group(0))
            ))

        # Match const/let/var declarations
        # const foo = ...
        var_pattern = r'(?:const|let|var)\s+(\w+)\s*='
        for match in re.finditer(var_pattern, source):
            line = source[:match.start()].count('\n') + 1
            col = match.start() - source[:match.start()].rfind('\n') - 1
            symbols.append(TreeSitterSymbol(
                name=match.group(1),
                kind="variable",
                line=line,
                col=col,
                end_line=line,
                end_col=col + len(match.group(0))
            ))

        return symbols

    def _extract_imports_regex(self, source: str) -> List[TreeSitterImport]:
        """
        Fallback: Extract imports using regex

        Args:
            source: Source code

        Returns:
            List of imports
        """
        import re
        imports = []

        # Match import statements
        # import { foo, bar } from 'module'
        # import foo from 'module'
        # import * as foo from 'module'
        import_pattern = r'import\s+(?:{([^}]+)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, source):
            line = source[:match.start()].count('\n') + 1

            if match.group(1):  # { foo, bar }
                names = [n.strip() for n in match.group(1).split(',')]
            elif match.group(2):  # foo
                names = [match.group(2)]
            elif match.group(3):  # * as foo
                names = [match.group(3)]
            else:
                names = []

            source_module = match.group(4)

            imports.append(TreeSitterImport(
                source=source_module,
                names=names,
                line=line
            ))

        return imports

    def get_file_symbols(self, file_path: str) -> List[TreeSitterSymbol]:
        """
        Get all symbols from a file

        Args:
            file_path: Path to file

        Returns:
            List of symbols
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            # Determine file type
            if file_path.endswith('.ts') or file_path.endswith('.tsx'):
                tree = self.parse_typescript(file_path)
            else:
                tree = self.parse_javascript(file_path)

            return self.extract_symbols(tree, source)
        except Exception:
            return []

    def get_file_imports(self, file_path: str) -> List[TreeSitterImport]:
        """
        Get all imports from a file

        Args:
            file_path: Path to file

        Returns:
            List of imports
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            # Determine file type
            if file_path.endswith('.ts') or file_path.endswith('.tsx'):
                tree = self.parse_typescript(file_path)
            else:
                tree = self.parse_javascript(file_path)

            return self.extract_imports(tree, source)
        except Exception:
            return []
