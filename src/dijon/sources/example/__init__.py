"""Example source adapter.

This module demonstrates the source discovery contract:
- Exports SOURCE_KEY and DATASET_CODE at module level (side-effect-free)
- Provides get_source() factory function for lazy initialization
- Does not import internal modules by default
"""

# Discovery symbols (must be at module level, no I/O)
SOURCE_KEY = "example"
DATASET_CODE = "EXM"

# Optional capabilities
CAPABILITIES = {
    "acquire": True,
    "ingest": True,
    "load": True,
}


def get_source():
    """Factory function that returns a configured source instance.
    
    This function may perform I/O (read config, create paths, etc.).
    Called only when the source is actually used, not during discovery.
    
    Returns:
        ExampleSource instance.
    """
    # Lazy import: only import when actually needed, not at module level
    from .adapter import ExampleSource
    
    return ExampleSource()

