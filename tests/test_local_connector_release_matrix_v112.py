from pathlib import Path
import unittest


class LocalConnectorReleaseMatrixV112TestCase(unittest.TestCase):
    def test_release_matrix_requires_windows_and_macos_artifacts(self) -> None:
        workflow = Path(".github/workflows/local-connector-release.yml").read_text(encoding="utf-8")
        self.assertIn("DSA-Local-Connector-Windows-x64.exe", workflow)
        self.assertIn("DSA-Local-Connector-macOS-arm64.dmg", workflow)
        self.assertIn("DSA-Local-Connector-macOS-x64.dmg", workflow)
        self.assertIn("LOCAL_CONNECTOR_SIGNING_NOT_READY", workflow)

    def test_build_scripts_fail_closed_when_tests_or_packaging_fail(self) -> None:
        windows = Path("apps/dsa-local-connector/build-windows.ps1").read_text(encoding="utf-8")
        macos = Path("apps/dsa-local-connector/build-macos.sh").read_text(encoding="utf-8")
        self.assertIn("if ($LASTEXITCODE -ne 0)", windows)
        self.assertIn("tests.test_user_local_connector_v112", windows)
        self.assertIn("(cd ../.. && python3 -m unittest tests.test_user_local_connector_v112)", macos)


if __name__ == "__main__":
    unittest.main()
