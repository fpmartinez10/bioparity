from __future__ import annotations

from . import register
from .table import Table


@register
class Metrics(Table):
    """Picard-style metrics files: `#` comment blocks are skipped, header row, tolerant floats."""

    name = "metrics"
    defaults = {"skip_prefixes": ["#"], "header": True}
