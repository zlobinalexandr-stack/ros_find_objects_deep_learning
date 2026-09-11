from __future__ import print_function

import fcntl
import json
import os
import shutil


class ObjectStore(object):
    """Persistent storage for uploaded compressed object templates."""

    def __init__(self, directory):
        self.directory = os.path.abspath(os.path.expanduser(directory))
        if not os.path.isdir(self.directory):
            os.makedirs(self.directory)
        lock_path = os.path.join(self.directory, '.migration.lock')
        with open(lock_path, 'a') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._migrate_reserved_zero_id()

    def ids(self):
        result = []
        for name in os.listdir(self.directory):
            if not name.endswith('.json'):
                continue
            try:
                object_id = int(name[:-5])
            except ValueError:
                continue
            if object_id > 0 and os.path.isfile(self._image_path(object_id)):
                result.append(object_id)
        return sorted(result)

    def allocate_id(self):
        used = set(self.ids())
        object_id = 1
        while object_id in used:
            object_id += 1
        return object_id

    def resolve_requested_id(self, requested_id):
        """Return the requested ID, allocating one for the automatic-ID markers."""
        requested_id = str(requested_id).strip()
        if requested_id in ('', '0'):
            return self.allocate_id()
        object_id = int(requested_id)
        if object_id <= 0:
            raise ValueError('object ID must be positive')
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

    def export_images(self, directory):
        """Write detector-readable image files, preserving their numeric names."""
        directory = os.path.abspath(os.path.expanduser(directory))
        if os.path.isdir(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)
        for object_id in self.ids():
            image_format, data = self.load(object_id)
            extension = self._image_extension(image_format, data)
            path = os.path.join(directory, '%08d.%s' % (object_id, extension))
            self._atomic_write(path, data, binary=True)

    @staticmethod
    def _image_extension(image_format, data):
        image_format = (image_format or '').lower().split(';', 1)[0].strip()
        if 'png' in image_format or data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        if ('jpeg' in image_format or 'jpg' in image_format or
                data.startswith(b'\xff\xd8')):
            return 'jpg'
        raise ValueError('unsupported compressed image format %r' % image_format)

    @staticmethod
    def _validate_id(object_id):
        object_id = int(object_id)
        if object_id <= 0:
            raise ValueError('object ID must be positive')
        return object_id

    def _migrate_reserved_zero_id(self):
        """Move legacy ID 0, which find_object_2d reserves for automatic IDs."""
        zero_metadata = os.path.join(self.directory, '0.json')
        zero_image = os.path.join(self.directory, '0.image')
        if not os.path.isfile(zero_metadata) or not os.path.isfile(zero_image):
            return
        target = 1
        while (os.path.exists(os.path.join(self.directory, '%d.json' % target)) or
               os.path.exists(os.path.join(self.directory, '%d.image' % target))):
            target += 1
        with open(zero_metadata, 'r') as metadata_file:
            metadata = json.load(metadata_file)
        metadata['id'] = target
        self._atomic_write(
            os.path.join(self.directory, '%d.json' % target),
            json.dumps(metadata, sort_keys=True).encode('utf-8'), binary=True)
        os.rename(zero_image, os.path.join(self.directory, '%d.image' % target))
        os.remove(zero_metadata)

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
