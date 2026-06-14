import sys
from unittest.mock import MagicMock

# Mocking Windows-specific modules for Linux environment testing
mock_wmi = MagicMock()
sys.modules["wmi"] = mock_wmi
mock_win32com = MagicMock()
sys.modules["win32com"] = mock_win32com
sys.modules["win32com.client"] = mock_win32com
mock_ctk = MagicMock()
sys.modules["customtkinter"] = mock_ctk

import unittest
import laptop_inspector

class TestInspector(unittest.TestCase):
    def test_scanner_instantiation(self):
        scanner = laptop_inspector.SystemScanner()
        self.assertIsNotNone(scanner)

    def test_cpu_info_structure(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_cpu_info()
        self.assertIn("الاسم", info)
        self.assertIn("التردد", info)

    def test_ram_info_structure(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_ram_info()
        self.assertIn("الإجمالي", info)

    def test_gpu_info_fallback(self):
        scanner = laptop_inspector.SystemScanner()
        # Should return a list even if GPUtil fails or no GPUs found
        info = scanner.get_gpu_info()
        self.assertIsInstance(info, list)
        self.assertTrue(len(info) > 0)

if __name__ == "__main__":
    unittest.main()
