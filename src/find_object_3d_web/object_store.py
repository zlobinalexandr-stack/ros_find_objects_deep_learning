from __future__ import print_function

import json
import os


class ObjectStore(object):
    """Persistent storage for uploaded compressed object templates."""

    def __init__(self, directory):
        self.directory = os.path.abspath(os.path.expanduser(directory))
        if not os.path.isdir(self.directory):
            os.makedirs(self.directory)

    def ids(self):
        result = []
        for name in os.listdir(self.directory):
            if not name.endswith('.json'):
                continue
            try:
                object_id = int(name[:-5])
            except ValueError:
                continue
            if object_id >= 0 and os.path.isfile(self._image_path(object_id)):
                result.append(object_id)
        return sorted(result)

    def allocate_id(self):
        used = set(self.ids())
        object_id = 0
        while object_id in used:
            object_id += 1
        return object_id

    def save(self, object_id, image_format, data):
        object_id = self._validate_id(object_id)
        metadata = {'id': object_id, 'format': image_format or ''}
        self._atomic_write(self._image_path(object_id), bytes(bytearray(data)), binary=True)
        self._atomic_write(
            self._metadata_path(object_id),
            json.dumps(metadata, sort_keys=True).encode('utf-8'), binary=True)

    def load(self, object_id):
        object_id = self._validate_id(object_id)
        with open(self._metadata_path(object_id), 'r') as metadata_file:
            metadata = json.load(metadata_file)
        with open(self._image_path(object_id), 'rb') as image_file:
            data = image_file.read()
        return metadata.get('format', ''), data

    def remove(self, object_id):
        object_id = self._validate_id(object_id)
        removed = False
        for path in (self._metadata_path(object_id), self._image_path(object_id)):
            try:
                os.remove(path)
                removed = True
            except OSError:
                pass
        return removed

    @staticmethod
    def _validate_id(object_id):
        object_id = int(object_id)
        if object_id < 0:
            raise ValueError('object ID must not be negative')
        return object_id

    def _metadata_path(self, object_id):
        return os.path.join(self.directory, '%d.json' % object_id)

    def _image_path(self, object_id):
        return os.path.join(self.directory, '%d.image' % object_id)

    @staticmethod
    def _atomic_write(path, data, binary=False):
        temporary_path = path + '.tmp'
        mode = 'wb' if binary else 'w'
        with open(temporary_path, mode) as output_file:
            output_file.write(data)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.rename(temporary_path, path)
