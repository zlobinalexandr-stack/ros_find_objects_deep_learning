from __future__ import division

import numpy as np


RECORD_SIZE = 12


class ExponentialPositionFilter(object):
    """Keep an exponential moving average of positions, independently by ID."""

    def __init__(self, smoothing_factor, reset_after):
        self.smoothing_factor = float(smoothing_factor)
        self.reset_after = float(reset_after)
        if (not np.isfinite(self.smoothing_factor) or
                self.smoothing_factor <= 0.0 or self.smoothing_factor > 1.0):
            raise ValueError('position smoothing factor must be in (0, 1]')
        if not np.isfinite(self.reset_after) or self.reset_after <= 0.0:
            raise ValueError('position filter reset time must be finite and positive')
        self._states = {}

    def update(self, object_id, position, stamp):
        """Return a filtered position, resetting after gaps or time jumps."""
        position = np.asarray(position, dtype=np.float64)
        if position.shape != (3,) or not np.all(np.isfinite(position)):
            raise ValueError('object position must contain three finite coordinates')
        stamp = float(stamp)
        if not np.isfinite(stamp):
            raise ValueError('position timestamp must be finite')

        previous = self._states.get(object_id)
        if (previous is None or stamp < previous[1] or
                stamp - previous[1] > self.reset_after):
            filtered = position
        else:
            filtered = (self.smoothing_factor * position +
                        (1.0 - self.smoothing_factor) * previous[0])
        self._states[object_id] = (filtered, stamp)
        return tuple(filtered)

    def reset(self, object_id):
        self._states.pop(object_id, None)


def calibrate_depth(depth, scale, offset):
    """Apply a metric affine calibration to scalar or array depth values."""
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('depth calibration scale must be finite and positive')
    if not np.isfinite(offset):
        raise ValueError('depth calibration offset must be finite')
    return np.asarray(depth) * scale + offset


def parse_detections(values):
    """Yield (id, template_width, template_height, 3x3 homography) records."""
    if len(values) % RECORD_SIZE:
        raise ValueError('find_object_2d data length must be a multiple of 12')
    for start in range(0, len(values), RECORD_SIZE):
        record = values[start:start + RECORD_SIZE]
        # find_object_2d serializes the homography one *column* at a time
        # (h11, h21, h31, h12, ...). NumPy reshapes flat arrays row-first,
        # therefore transpose the intermediate matrix. Treating the wire
        # representation as row-major moves the translation into the
        # projective denominator and makes detections project near (0, 0).
        homography = np.asarray(record[3:12], dtype=np.float64).reshape((3, 3)).T
        yield int(record[0]), record[1], record[2], homography


def projected_center(width, height, homography):
    point = np.dot(homography, np.asarray([width / 2.0, height / 2.0, 1.0]))
    if abs(point[2]) < 1e-12:
        raise ValueError('homography projects the object center to infinity')
    return point[0] / point[2], point[1] / point[2]


def robust_depth(depth, u, v, radius, minimum, maximum):
    """Return the median finite depth in a square window, or None."""
    height, width = depth.shape[:2]
    x0, x1 = max(0, int(round(u)) - radius), min(width, int(round(u)) + radius + 1)
    y0, y1 = max(0, int(round(v)) - radius), min(height, int(round(v)) + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return None
    values = np.asarray(depth[y0:y1, x0:x1], dtype=np.float64).reshape(-1)
    values = values[np.isfinite(values)]
    values = values[(values >= minimum) & (values <= maximum)]
    return None if not values.size else float(np.median(values))


def project_pixel(u, v, depth, camera_info):
    """Project a rectified image pixel using CameraInfo's pinhole matrix."""
    fx, fy = camera_info.K[0], camera_info.K[4]
    cx, cy = camera_info.K[2], camera_info.K[5]
    if not all(np.isfinite(x) for x in (fx, fy, cx, cy)) or fx == 0 or fy == 0:
        raise ValueError('invalid camera intrinsic matrix')
    return ((u - cx) * depth / fx, (v - cy) * depth / fy, depth)
