"""Quro documentation — shipped as package data in the wheel.

This file is minimal; the real content is the .md / .json files carried as
package-data.  The docs_root() helper in cli/commands/docs.py is the
canonical entry point for locating docs on disk in both editable and wheel
installs.  Don't import this module for anything else.
"""
__path__ = __import__("pathlib").Path(__file__).parent.resolve()
