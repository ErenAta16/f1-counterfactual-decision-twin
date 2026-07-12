"""Project-local storage conventions for reproducible research artefacts."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    """Filesystem locations that are intentionally excluded from source control."""

    root: Path
    fastf1_cache: Path
    processed: Path
    manifests: Path
    quality_reports: Path

    @classmethod
    def from_root(cls, root: Path) -> "DataPaths":
        root = root.expanduser().resolve()
        return cls(
            root=root,
            fastf1_cache=root / "cache" / "fastf1",
            processed=root / "processed",
            manifests=root / "manifests",
            quality_reports=root / "quality",
        )

    def create(self) -> None:
        """Create the local-only storage directories used by the ingest command."""

        for directory in (self.fastf1_cache, self.processed, self.manifests, self.quality_reports):
            directory.mkdir(parents=True, exist_ok=True)


def default_data_root() -> Path:
    """Return a configurable data root without storing data in the repository history."""

    configured_root = os.environ.get("APEXMIND_DATA_DIR")
    if configured_root:
        return Path(configured_root)
    return Path(__file__).resolve().parents[2] / "work" / "data"
