from __future__ import annotations

import builtins
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


class FeishuSenderImportResilienceTestCase(unittest.TestCase):
    def test_lark_oapi_oserror_keeps_sdk_disabled(self) -> None:
        root = Path(__file__).resolve().parents[1]
        module_path = root / "src" / "notification_sender" / "feishu_sender.py"
        spec = importlib.util.spec_from_file_location("feishu_sender_import_probe", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "lark_oapi" or name.startswith("lark_oapi."):
                raise OSError("simulated Windows socket buffer exhaustion")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            spec.loader.exec_module(module)

        self.assertFalse(module.FEISHU_SDK_AVAILABLE)
        self.assertIsNone(module._lark)


if __name__ == "__main__":
    unittest.main()
