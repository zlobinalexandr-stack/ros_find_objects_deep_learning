from __future__ import print_function

import json
import os
import shutil
import tempfile
import unittest

from find_object_3d_web.object_store import ObjectStore


class ObjectStoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.store = ObjectStore(self.directory)

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_save_load_list_and_remove(self):
        self.store.save(7, 'jpeg', bytearray([0xff, 0xd8, 0xff, 0xd9]))
        self.assertEqual([7], self.store.ids())
        self.assertEqual(('jpeg', b'\xff\xd8\xff\xd9'), self.store.load(7))
        self.assertTrue(self.store.remove(7))
        self.assertEqual([], self.store.ids())
        self.assertFalse(self.store.remove(7))

    def test_allocate_lowest_available_id(self):
        self.store.save(1, 'jpeg', b'one')
        self.store.save(3, 'png', b'three')
        self.assertEqual(2, self.store.allocate_id())

    def test_rejects_negative_id(self):
        with self.assertRaises(ValueError):
            self.store.save(-1, 'jpeg', b'image')

    def test_rejects_reserved_zero_id(self):
        with self.assertRaises(ValueError):
            self.store.save(0, 'jpeg', b'image')

    def test_migrates_legacy_zero_id(self):
        with open(os.path.join(self.directory, '0.image'), 'wb') as image_file:
            image_file.write(b'legacy')
        with open(os.path.join(self.directory, '0.json'), 'w') as metadata_file:
            json.dump({'id': 0, 'format': 'jpeg'}, metadata_file)

        migrated = ObjectStore(self.directory)

        self.assertEqual([1], migrated.ids())
        self.assertEqual(('jpeg', b'legacy'), migrated.load(1))
        self.assertFalse(os.path.exists(os.path.join(self.directory, '0.image')))


if __name__ == '__main__':
    unittest.main()
