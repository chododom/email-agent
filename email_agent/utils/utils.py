import importlib
import importlib.metadata

from pathlib import Path


def get_package_root(package_name: str) -> Path:
    """Get the root directory of a given package."""
    root = importlib.resources.files(package_name)
    assert isinstance(root, Path), f"Expected Path, got {type(root)}"
    return root


def get_version() -> str:
    return importlib.metadata.version(__package__ or __name__)
