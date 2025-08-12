from __future__ import annotations

from ..core.preprocess import apply_preprocess as core_apply_preprocess


def apply_preprocess(frame, cfg: dict):
    # Thin wrapper to keep service-level namespace aligned with camera service
    return core_apply_preprocess(frame, cfg)


