"""
Check registry.

Each Check01..Check19 class is exposed as a key in REGISTRY. The CLI
and the test harness iterate REGISTRY rather than importing checks by
hand so adding a new check is a one-line registration.
"""
from __future__ import annotations

from typing import Type

from .base import CheckRunner

# Imported individually so the runner gives a clean ImportError naming the
# missing check rather than a list of failed star-imports.
from .check01 import Check01
from .check02 import Check02
from .check03 import Check03
from .check04 import Check04
from .check05 import Check05
from .check06 import Check06
from .check07 import Check07
from .check08 import Check08
from .check09 import Check09
from .check10 import Check10
from .check11 import Check11
from .check12 import Check12
from .check13 import Check13
from .check14 import Check14
from .check15 import Check15
from .check16 import Check16
from .check17 import Check17
from .check18 import Check18
from .check19 import Check19


REGISTRY: dict[str, Type[CheckRunner]] = {
    cls.check_id: cls
    for cls in (
        Check01, Check02, Check03, Check04, Check05,
        Check06, Check07, Check08, Check09, Check10,
        Check11, Check12, Check13, Check14, Check15,
        Check16, Check17, Check18, Check19,
    )
}


__all__ = ["REGISTRY", "CheckRunner"]
