from __future__ import print_function

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
        self.store.save(0, 'jpeg', b'zero')
        self.store.save(2, 'png', b'two')
        self.assertEqual(1, self.store.allocate_id())

    def test_rejects_negative_id(self):
        with self.assertRaises(ValueError):
            self.store.save(-1, 'jpeg', b'image')


if __name__ == '__main__':
    unittest.main()
