"""
Derived comfort/heat-stress targets, shared by the producer and processor.

Kept byte-for-byte compatible with the original `nasa_power_data.py` so the
station CSVs produced here match the dataset the training notebooks already use.
(The LSTM notebook may *additionally* redefine WindChill as an Apparent
Temperature at feature-engineering time; the raw producer keeps the documented
NWS formulas.)
"""

from __future__ import annotations

import numpy as np


def heat_index(tmax_c, rh):
    """NWS heat index (°C). Uses the simple form below 80°F, full regression above."""
    tf = tmax_c * 1.8 + 32.0
    hi_simple = 0.5 * (tf + 61.0 + ((tf - 68.0) * 1.2) + (rh * 0.094))
    hi_full = (-42.379 + 2.04901523 * tf + 10.14333127 * rh - 0.22475541 * tf * rh
               - 0.00683783 * tf ** 2 - 0.05481717 * rh ** 2 + 0.00122874 * tf ** 2 * rh
               + 0.00085282 * tf * rh ** 2 - 0.00000199 * tf ** 2 * rh ** 2)
    hi_f = np.where(tf >= 80, hi_full, hi_simple)
    return (hi_f - 32.0) / 1.8


def wind_chill(tmin_c, wind_speed_ms):
    """NWS wind chill (°C). Falls back to air temperature when wind ≤ 3 mph."""
    v_mph = wind_speed_ms * 2.23694
    tf_min = tmin_c * 1.8 + 32.0
    wc_f = 35.74 + 0.6215 * tf_min - 35.75 * (v_mph ** 0.16) + 0.4275 * tf_min * (v_mph ** 0.16)
    wc_f = np.where(v_mph > 3.0, wc_f, tf_min)
    return (wc_f - 32.0) / 1.8
