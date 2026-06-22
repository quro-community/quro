"""
Setup configuration for quro
"""
from setuptools import setup, find_packages

setup(
    name="quro",
    version="0.1.0",
    description="Python-native MCP server with TypeScript probe integration",
    packages=find_packages(exclude=["*.venv", ".venv", "venv"]),
    package_dir={"": "."},
    python_requires=">=3.11",
    install_requires=[
        "click>=8.1.0",
        "asyncpg>=0.29.0",
        "datasketch>=1.6.0",
        "mcp>=0.9.0",
        "tree-sitter>=0.21.0",
        "tree-sitter-typescript>=0.21.0",
        "GitPython>=3.1.0",
        "httpx>=0.27.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "black>=24.0.0",
            "mypy>=1.8.0",
            "ruff>=0.2.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "quro=cli.main:main",
        ]
    },
)
