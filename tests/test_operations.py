"""Non-destructive unit tests. Real packages are never removed."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "usr/lib/cinnamon-remove-application/operations.py"
spec = importlib.util.spec_from_file_location("operations", SOURCE)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class TestPacman(unittest.TestCase):
    def test_owner(self):
        fake = subprocess.CompletedProcess([], 0, "rhythmbox\n", "")
        with patch.object(ops, "run", return_value=fake):
            self.assertEqual(ops.package_owner("/usr/share/applications/rhythmbox.desktop"),
                             "rhythmbox")

    def test_unowned(self):
        fake = subprocess.CompletedProcess([], 1, "", "")
        with patch.object(ops, "run", return_value=fake):
            self.assertIsNone(ops.package_owner("/tmp/example.desktop"))

    def test_preview_includes_dependents_and_dependencies(self):
        fake = subprocess.CompletedProcess([], 0, "app\ndep\nother\ndep\n", "")
        with patch.object(ops, "run", return_value=fake) as runner:
            self.assertEqual(ops.removal_plan("app"), ["app", "dep", "other"])
            self.assertIn("-Rcsp", runner.call_args.args[0])

    def test_preview_failure(self):
        fake = subprocess.CompletedProcess([], 1, "", "error")
        with patch.object(ops, "run", return_value=fake):
            with self.assertRaises(ops.RemovalError):
                ops.removal_plan("app")

    def test_core_system_protection(self):
        self.assertEqual(ops.protected_in(["app", "cinnamon"]), ["cinnamon"])
        with self.assertRaises(ops.RemovalError):
            ops.removal_command(["app", "cinnamon"])

    def test_exact_approved_set(self):
        approved = ["app", "other", "dep"]
        command = ops.removal_command(approved)
        self.assertEqual(command[:3], [ops.PKEXEC, ops.PACMAN, "-R"])
        self.assertEqual(command[command.index("--") + 1:], approved)
        self.assertNotIn("-Rc", command)
        self.assertNotIn("-Rs", command)

    def test_no_shell_injection(self):
        with self.assertRaises(ops.RemovalError):
            ops.removal_command(["app; rm -rf /"])

    def test_flatpak(self):
        with tempfile.TemporaryDirectory() as root:
            desktop = Path(root) / "org.example.App.desktop"
            desktop.write_text("[Desktop Entry]\nName=Example\nX-Flatpak=org.example.App\n")
            fake = subprocess.CompletedProcess([], 0, "app/org.example.App/x86_64/stable", "")
            with patch.object(ops.os.path, "isfile", return_value=True), \
                 patch.object(ops, "run", return_value=fake):
                self.assertEqual(ops.flatpak_target(str(desktop)),
                                 ("org.example.App", "--user"))

    def test_no_arbitrary_file_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            desktop = Path(root) / "example.desktop"
            desktop.write_text("[Desktop Entry]\nName=Example\n")
            with self.assertRaises(ops.RemovalError):
                ops.unowned_launcher_command(str(desktop))


if __name__ == "__main__":
    unittest.main()

