"""Example source adapter implementation."""

from __future__ import annotations

from pathlib import Path

from ...global_config import (
    ACQUISITION_DIR,
    ANNOTATIONS_DIR,
    NORMAL_DIR,
    RAW_DIR,
)


class ExampleSource:
    """Example source adapter for demonstration purposes."""

    def __init__(self) -> None:
        """Initialize the example source.
        
        This method may perform I/O (read config, create paths, etc.).
        Called only when the source is actually used, not during discovery.
        """
        self.source_key = "example"
        self.dataset_code = "EXM"

    def get_acquisition_dir(self) -> Path:
        """Get the acquisition directory for this source.
        
        Returns: data/acquisition/<source_key>/
        """
        return ACQUISITION_DIR / self.source_key

    def get_raw_dir(self) -> Path:
        """Get the raw directory for this source.
        
        Returns: data/raw/<source_key>/
        """
        return RAW_DIR / self.source_key

    def get_normal_dir(self) -> Path:
        """Get the normal directory for this source.
        
        Returns: data/normal/<source_key>/
        """
        return NORMAL_DIR / self.source_key

    def get_annotations_dir(self) -> Path:
        """Get the annotations directory for this source.
        
        Returns: data/annotations/<source_key>/
        """
        return ANNOTATIONS_DIR / self.source_key

    def get_manifest_path(self) -> Path:
        """Get the manifest path for this source.
        
        Manifests are metadata files that track raw data, so they live alongside
        the raw files they track.
        
        Returns: data/raw/<source_key>/manifest.csv
        """
        return self.get_raw_dir() / "manifest.csv"

