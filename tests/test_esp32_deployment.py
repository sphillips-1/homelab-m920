"""Exercise the real packaging and flash orchestration without any USB writes."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load('package_esp32', 'package-esp32-firmware.py')
flasher = load('deploy_esp32', 'deploy-esp32-firmware.py')
SHA = 'a' * 40
MAC = '48:9d:31:c0:27:5c'


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / 'build'
        self.build.mkdir()
        self.artifact = self.root / 'artifact'
        self.backups = self.root / 'backups'
        for name, _, _ in packager.PARTS:
            (self.build / name).write_bytes(name.encode() * 10)
        packager.package(self.build, self.build / 'boot_app0.bin', self.artifact, SHA)
        # Lock implementation is Linux-specific; do not require Linux for unit tests.
        fake_lock = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None)
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {'fcntl': fake_lock}).start()
        self.original_umask = flasher.os.umask(0o077)
        self.addCleanup(flasher.os.umask, self.original_umask)

    def record(self):
        return json.loads(next(self.backups.glob('*/deployment.json')).read_text())

    def tool(self, port, *args):
        if args[0] == 'read-mac':
            return f'MAC: {MAC}\n'
        if args[0] == 'read-flash':
            Path(args[-1]).write_bytes(b'\xff' * 0x400000)
        return ''

    def test_package_preserves_nvs_and_is_tied_to_commit(self):
        _, args = flasher.validate_artifact(self.artifact, SHA)
        self.assertEqual(args[::2], ['0x1000', '0x8000', '0xe000', '0x10000'])
        for _, offset, size in flasher.PARTS:
            self.assertTrue(offset + size <= 0x9000 or offset >= 0xE000)
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, 'b' * 40)

    def test_waveshare_uses_its_own_layout_and_preserves_nvs(self):
        target = 'waveshare-s3-touch-169'
        packager.package(self.build, self.build / 'boot_app0.bin', self.artifact, SHA, target)
        manifest, args = flasher.validate_artifact(self.artifact, SHA, target)
        self.assertEqual(manifest['chip'], 'esp32s3')
        self.assertEqual(manifest['flash_size'], 0x1000000)
        self.assertEqual(args[::2], ['0x0', '0x8000', '0xe000', '0x10000'])
        for _, offset, size in packager.BOARDS[target].parts:
            self.assertTrue(offset + size <= 0x9000 or offset >= 0xE000)
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, SHA)

    def test_waveshare_backs_up_and_verifies_the_16mb_board(self):
        target = 'waveshare-s3-touch-169'
        packager.package(self.build, self.build / 'boot_app0.bin', self.artifact, SHA, target)

        def native_tool(port, command, *args, chip):
            self.assertEqual(chip, 'esp32s3')
            if command == 'flash-id':
                return 'Detected flash size: 16MB'
            if command == 'read-flash':
                self.assertEqual(args[:2], ('0', '0x1000000'))
                with Path(args[-1]).open('wb') as backup:
                    backup.truncate(0x1000000)
            return self.tool(port, command, *args) if command != 'read-flash' else ''

        with patch.object(flasher, 'esptool', side_effect=native_tool) as tool, \
                patch.object(flasher, 'check_boot') as boot:
            flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA, target)
        self.assertEqual(self.record()['status'], 'deployed')
        write = next(call.args for call in tool.call_args_list if call.args[1] == 'write-flash')
        self.assertEqual(write[2::2], ('0x0', '0x8000', '0xe000', '0x10000'))
        boot.assert_called_once_with('USB', native_usb=True)

    def test_corrupt_binary_never_opens_usb(self):
        (self.artifact / 'firmware.bin').write_bytes(b'corrupted')
        with patch.object(flasher, 'esptool') as tool, self.assertRaises(ValueError):
            flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        tool.assert_not_called()

    def test_corrupt_binary_never_contacts_ota_target(self):
        (self.artifact / 'firmware.bin').write_bytes(b'corrupted')
        with patch.object(flasher.socket, 'socket') as socket, self.assertRaises(ValueError):
            flasher.deploy_ota(self.artifact, SHA, '192.168.4.63', 'c' * 64)
        socket.assert_not_called()

    def test_cyd_artifacts_are_bound_to_their_targets(self):
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, SHA, 'cyd-ant')
        packager.package(self.build, self.build / 'boot_app0.bin', self.artifact, SHA, 'cyd-ant')
        flasher.validate_artifact(self.artifact, SHA, 'cyd-ant')
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, SHA)
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, SHA, 'cyd-cat')
        packager.package(self.build, self.build / 'boot_app0.bin', self.artifact, SHA, 'cyd-cat')
        flasher.validate_artifact(self.artifact, SHA, 'cyd-cat')

    def test_ota_uses_lan_callback_and_fails_on_uploader_error(self):
        uploader = Mock(return_value=1)
        with patch.object(flasher.runpy, 'run_path', return_value={'main': uploader}), \
                patch.object(flasher.socket, 'socket') as socket, self.assertRaises(RuntimeError):
            route = socket.return_value.__enter__.return_value
            route.getsockname.return_value = ('192.168.4.27', 62000)
            flasher.deploy_ota(self.artifact, SHA, '192.168.4.63', 'c' * 64)
        route.connect.assert_called_once_with(('192.168.4.63', 3232))
        uploader.assert_called_once_with(['-i', '192.168.4.63', '-I', '192.168.4.27',
                                          '-P', '3233', '-t', '3', '-a', 'c' * 64,
                                          '-f', str(self.artifact / 'firmware.bin')])

    def test_changed_offset_is_rejected(self):
        manifest = self.artifact / 'manifest.json'
        data = json.loads(manifest.read_text())
        data['images'][0]['offset'] = 0x9000
        manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            flasher.validate_artifact(self.artifact, SHA)

    def test_wrong_board_never_backs_up_or_writes(self):
        with patch.object(flasher, 'esptool', return_value='MAC: 00:00:00:00:00:00') as tool:
            with self.assertRaises(ValueError):
                flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        self.assertEqual(tool.call_count, 1)
        self.assertFalse(list(self.backups.glob('*/previous-flash.bin')))

    def test_incomplete_backup_refuses_flash(self):
        def incomplete(port, *args):
            if args[0] == 'read-flash':
                Path(args[-1]).write_bytes(b'short')
                return ''
            return self.tool(port, *args)
        with patch.object(flasher, 'esptool', side_effect=incomplete) as tool:
            with self.assertRaises(RuntimeError):
                flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        self.assertNotIn('write-flash', [call.args[1] for call in tool.call_args_list])

    def test_success_verifies_images_and_boot(self):
        with patch.object(flasher, 'esptool', side_effect=self.tool) as tool, \
                patch.object(flasher, 'check_boot') as boot:
            flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        self.assertEqual(self.record()['status'], 'deployed')
        self.assertIn('verify-flash', [call.args[1] for call in tool.call_args_list])
        boot.assert_called_once_with('USB')

    def test_failed_boot_restores_backup_and_still_fails_job(self):
        with patch.object(flasher, 'esptool', side_effect=self.tool) as tool, \
                patch.object(flasher, 'check_boot', side_effect=RuntimeError('crashed')):
            with self.assertRaises(RuntimeError):
                flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        self.assertEqual(self.record()['status'], 'rolled-back')
        writes = [call.args for call in tool.call_args_list if call.args[1] == 'write-flash']
        self.assertEqual(writes[-1][2], '0')
        self.assertEqual(writes[-1][3].name, 'previous-flash.bin')

    def test_failed_rollback_is_recorded(self):
        def bad_write(port, *args):
            if args[0] == 'write-flash':
                raise RuntimeError('disconnected')
            return self.tool(port, *args)
        with patch.object(flasher, 'esptool', side_effect=bad_write):
            with self.assertRaises(RuntimeError):
                flasher.deploy(self.artifact, self.backups, 'USB', MAC, SHA)
        self.assertEqual(self.record()['status'], 'rollback-failed')


if __name__ == '__main__':
    unittest.main()
