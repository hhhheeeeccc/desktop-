import sys
from unittest.mock import MagicMock, patch

# Mock all potentially missing dependencies
mock_wmi = MagicMock()
sys.modules["wmi"] = mock_wmi
mock_win32com = MagicMock()
sys.modules["win32com"] = mock_win32com
sys.modules["win32com.client"] = mock_win32com
mock_ctk = MagicMock()
sys.modules["customtkinter"] = mock_ctk
mock_cpuinfo = MagicMock()
sys.modules["cpuinfo"] = mock_cpuinfo
mock_gputil = MagicMock()
sys.modules["GPUtil"] = mock_gputil
mock_psutil = MagicMock()
sys.modules["psutil"] = mock_psutil

import unittest
import laptop_inspector

class TestInspector(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_psutil.reset_mock()
        mock_cpuinfo.get_cpu_info.return_value = {'brand_raw': 'Intel Core i7', 'hz_actual_friendly': '2.5 GHz', 'arch': 'X86_64'}
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value.total = 16 * 1024**3
        mock_psutil.virtual_memory.return_value.used = 8 * 1024**3
        mock_psutil.virtual_memory.return_value.available = 8 * 1024**3
        mock_psutil.virtual_memory.return_value.percent = 50
        mock_psutil.sensors_battery.return_value.percent = 85
        mock_psutil.sensors_battery.return_value.power_plugged = True
        mock_psutil.sensors_battery.return_value.secsleft = 3600
        mock_psutil.disk_partitions.return_value = [MagicMock(device='/dev/sda1', mountpoint='/', opts='rw', fstype='ext4')]
        mock_psutil.disk_usage.return_value.total = 500 * 1024**3
        mock_psutil.sensors_temperatures.return_value = {'coretemp': [MagicMock(current=45.0)]}

    def test_scanner_instantiation(self):
        scanner = laptop_inspector.SystemScanner()
        self.assertIsNotNone(scanner)

    def test_cpu_info_structure(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_cpu_info()
        self.assertEqual(info["الاسم"], "Intel Core i7")
        self.assertEqual(info["الأنوية الحقيقية"], 8)

    def test_ram_info_structure(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_ram_info()
        self.assertEqual(info["الإجمالي"], "16.00 GB")

    def test_gpu_info_fallback(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_gpu_info()
        self.assertIsInstance(info, list)
        self.assertTrue(len(info) > 0)

    def test_battery_info_linux(self):
        scanner = laptop_inspector.SystemScanner()
        # Force linux behavior if needed, but the mock should handle it
        info = scanner.get_battery_info()
        self.assertEqual(info["النسبة المئوية"], "85%")

    def test_storage_info_linux(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_storage_info()
        self.assertTrue(any(d["الموديل"] == "/dev/sda1" for d in info))

    def test_temperature_info_linux(self):
        scanner = laptop_inspector.SystemScanner()
        info = scanner.get_temperature_info()
        self.assertEqual(info["CPU"], "45.0 °C")

if __name__ == "__main__":
    unittest.main()
