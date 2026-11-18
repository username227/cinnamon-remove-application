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

    def test_default_preview_removes_only_selected_application(self):
        fake = subprocess.CompletedProcess([], 0, "app\n", "")
        with patch.object(ops, "run", return_value=fake) as runner:
            self.assertEqual(ops.removal_plan("app"), ["app"])
            self.assertEqual(runner.call_args.args[0],
                             [ops.PACMAN, "-Rp", "--print-format", "%n", "--", "app"])

    def test_opted_in_preview_includes_newly_unused_dependencies(self):
        fake = subprocess.CompletedProcess([], 0, "app\ndep\ndep\n", "")
        with patch.object(ops, "run", return_value=fake) as runner:
            self.assertEqual(ops.removal_plan("app", include_unused=True),
                             ["app", "dep"])
            self.assertEqual(runner.call_args.args[0],
                             [ops.PACMAN, "-Rsp", "--print-format", "%n", "--", "app"])
            self.assertNotIn("c", runner.call_args.args[0][1])

    def test_preview_failure(self):
        fake = subprocess.CompletedProcess([], 1, "", "error")
        with patch.object(ops, "run", return_value=fake):
            with self.assertRaises(ops.RemovalError):
                ops.removal_plan("app")

    def test_direct_reverse_dependents_reported_for_explanation(self):
        info = (
            "Name            : shared-lib\n"
            "Required By     : desktop-tool media-player\n"
            "                  backup-client\n"
            "Optional For    : None\n"
        )
        fake = subprocess.CompletedProcess([], 0, info, "")
        with patch.object(ops, "run", return_value=fake) as runner:
            self.assertEqual(ops.required_by("shared-lib"),
                             ["desktop-tool", "media-player", "backup-client"])
            self.assertEqual(runner.call_args.args[0],
                             [ops.PACMAN, "-Qi", "--", "shared-lib"])
            self.assertTrue(runner.call_args.kwargs["c_locale"])

    def test_reverse_dependents_none_and_query_failure(self):
        for result in (
            subprocess.CompletedProcess([], 0, "Required By     : None\n", ""),
            subprocess.CompletedProcess([], 1, "", "package not found"),
        ):
            with patch.object(ops, "run", return_value=result):
                self.assertEqual(ops.required_by("shared-lib"), [])

    def test_reverse_dependents_are_never_removal_targets(self):
        fake = subprocess.CompletedProcess(
            [], 0, "Required By     : cinnamon other-app\n", "")
        with patch.object(ops, "run", return_value=fake):
            self.assertEqual(ops.required_by("shared-lib"), ["cinnamon", "other-app"])
        # This diagnostic cannot expand the actual pacman transaction.
        self.assertEqual(ops.removal_command(["shared-lib"])[-1:], ["shared-lib"])

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

    def test_flatpak_unused_cleanup_scoped_explicitly(self):
        self.assertEqual(
            ops.flatpak_unused_command("--user"),
            [ops.FLATPAK, "uninstall", "--user", "--unused",
             "--noninteractive", "--assumeyes"])
        self.assertEqual(
            ops.flatpak_unused_command("--system"),
            [ops.FLATPAK, "uninstall", "--system", "--unused",
             "--noninteractive", "--assumeyes"])
        for bad in ("", "--all", "--installation=other", "--system --delete-data"):
            with self.assertRaises(ops.RemovalError):
                ops.flatpak_unused_command(bad)

    def test_flatpak_removal_never_deletes_user_data(self):
        for name, scope in (("org.example.App", "--user"),
                            ("org.example.App", "--system")):
            cmd = ops.flatpak_removal_command(name, scope)
            self.assertNotIn("--delete-data", cmd)
            self.assertNotIn("--unused", cmd)

    def test_no_arbitrary_file_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            desktop = Path(root) / "example.desktop"
            desktop.write_text("[Desktop Entry]\nName=Example\n")
            with self.assertRaises(ops.RemovalError):
                ops.unowned_launcher_command(str(desktop))


if __name__ == "__main__":
    unittest.main()

