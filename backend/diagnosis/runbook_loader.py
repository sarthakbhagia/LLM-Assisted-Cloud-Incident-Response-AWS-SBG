"""
runbook_loader.py — Phase 4: Runbook Context Loader

Simple lookup utility that takes fault_class and returns the matching
procedural runbook text from knowledge_base/.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_runbook(fault_class: str) -> str:
    """
    Load the runbook text for the given fault_class.

    Searches in:
      1. ./knowledge_base/<fault_class>.md (relative to module directory)
      2. ../../knowledge_base/<fault_class>.md (relative to workspace root)
      3. /tmp or fallback
    """
    filename = f"{fault_class}.md"
    module_dir = Path(__file__).resolve().parent

    candidate_paths = [
        module_dir / "knowledge_base" / filename,
        module_dir.parent.parent / "knowledge_base" / filename,
        Path(os.getcwd()) / "knowledge_base" / filename,
    ]

    for path in candidate_paths:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                logger.info(f"Loaded runbook for {fault_class} from {path}")
                return content
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to read runbook at {path}: {exc}")

    logger.warning(f"No runbook file found for fault_class={fault_class}")
    return f"# Default Runbook for {fault_class}\nNo specific runbook available."
