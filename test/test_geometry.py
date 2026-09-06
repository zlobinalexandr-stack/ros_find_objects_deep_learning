#!/usr/bin/env python
import unittest

import numpy as np

from find_object_3d_web.geometry import parse_detections, projected_center, project_pixel, robust_depth


class CameraInfo(object):
    K = [500.0, 0.0, 320.0, 0.0, 500.0, 240.0, 0.0, 0.0, 1.0]


class GeometryTest(unittest.TestCase):
    def test_detection_and_homography_center(self):
        records = list(parse_detections([7, 20, 10, 1, 0, 100, 0, 1, 50, 0, 0, 1]))
        self.assertEqual(records[0][0], 7)
        self.assertEqual(projected_center(records[0][1], records[0][2], records[0][3]), (110.0, 55.0))

    def test_malformed_detection(self):
        with self.assertRaises(ValueError):
            list(parse_detections([1, 2]))

    def test_robust_depth_rejects_invalid_values(self):
        depth = np.asarray([[np.nan, 2.0, 50.0], [1.0, 3.0, np.inf]])
        self.assertEqual(robust_depth(depth, 1, 0, 1, 0.1, 10.0), 2.0)
        self.assertIsNone(robust_depth(depth, -20, -20, 1, 0.1, 10.0))

    def test_pixel_projection(self):
        self.assertEqual(project_pixel(420, 290, 2.0, CameraInfo()), (0.4, 0.2, 2.0))


if __name__ == '__main__':
    unittest.main()
