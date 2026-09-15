import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('install-models.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Response(io.BytesIO):
    def geturl(self):
        return 'https://example.test/weight'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'models/weight'
        self.manifest = {'models': [{'relativePath': 'models/weight', 'bytes': 3,
                                    'publishedSha256': hashlib.sha256(b'abc').hexdigest(),
                                    'downloadUrl': 'https://example.test/weight'}]}

    def install(self, data=b'abc'):
        return installer.install(self.root, self.manifest, lambda *a, **kw: Response(data))

    def test_install_then_reuse_without_network(self):
        self.assertEqual(self.install()['models'][0]['action'], 'installed')
        self.assertEqual(self.path.read_bytes(), b'abc')
        result = installer.install(self.root, self.manifest, lambda *a, **kw: self.fail('Network used for valid existing model'))
        self.assertEqual(result['models'][0]['action'], 'reused')

    def test_bad_downloads_never_publish(self):
        for data in (b'ab', b'abcd', b'bad'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.install(data)
            self.assertFalse(self.path.exists())
            self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_existing_wrong_file_and_broken_link_are_preserved(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b'bad')
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(self.path.read_bytes(), b'bad')
        self.path.unlink()
        self.path.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError):
            self.install()
        self.assertTrue(self.path.is_symlink())

    def test_interruption_cleans_partial_and_can_retry(self):
        class Interrupted(Response):
            def read(self, *args):
                raise OSError('Connection interrupted')
        with self.assertRaises(OSError):
            installer.install(self.root, self.manifest, lambda *a, **kw: Interrupted(b''))
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])
        self.assertTrue(self.install()['ok'])

    def test_concurrent_destination_never_overwritten(self):
        def opener(*args, **kwargs):
            self.path.write_bytes(b'other installation')
            return Response(b'abc')
        with self.assertRaises(FileExistsError):
            installer.install(self.root, self.manifest, opener)
        self.assertEqual(self.path.read_bytes(), b'other installation')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_manifest_and_redirect_validation(self):
        self.manifest['models'][0]['relativePath'] = '../outside'
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(list(self.root.iterdir()), [])
        self.manifest['models'][0]['relativePath'] = 'models/weight'
        class Insecure(Response):
            def geturl(self):
                return 'http://example.test/weight'
        with self.assertRaises(ValueError):
            installer.install(self.root, self.manifest, lambda *a, **kw: Insecure(b'abc'))
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
