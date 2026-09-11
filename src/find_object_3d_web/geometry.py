from __future__ import division

import numpy as np


RECORD_SIZE = 12


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
