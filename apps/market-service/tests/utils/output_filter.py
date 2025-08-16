#!/usr/bin/env python3
"""Filter out network-related noise from test output"""

import sys

# Patterns to filter out
FILTER_PATTERNS = [
    "br-",
    "docker0:",
    "WARNING: you should run this program",
    "WARNING: output may be incomplete",
    "/sys/firmware/dmi/",
    "/dev/mem:",
]

for line in sys.stdin:
    # Check if line contains any filter pattern
    should_filter = False
    for pattern in FILTER_PATTERNS:
        if pattern in line:
            should_filter = True
            break

    if not should_filter:
        print(line, end="")
