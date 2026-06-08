"""MiniSFS shared constants.

Central location for magic numbers and configuration values
extracted from across the project during refactoring.
"""

import math

# ============================================================================
# Math Constants
# ============================================================================

# 2 * pi — used in angle normalization and orbital detection
TWO_PI: float = 2.0 * math.pi

# Epsilon for angle comparison
ANGLE_NORMALIZE_EPSILON: float = 1e-12
