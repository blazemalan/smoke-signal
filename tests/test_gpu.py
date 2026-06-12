import unittest
from unittest.mock import patch, MagicMock

import pytest

torch = pytest.importorskip("torch", reason="gpu module requires torch")

from smoke_signal.gpu import check_gpu, estimate_vram, check_vram_sufficient

class TestGPU(unittest.TestCase):

    @patch('torch.cuda.is_available')
    @patch('torch.backends.mps.is_available', create=True)
    def test_check_gpu_cpu_only(self, mock_mps_is_available, mock_cuda_is_available):
        mock_cuda_is_available.return_value = False
        mock_mps_is_available.return_value = False

        # In case the attribute does not exist at all, we can mock builtins.hasattr
        with patch('builtins.hasattr', return_value=False):
            result = check_gpu()

        self.assertEqual(result['available'], False)
        self.assertEqual(result['device'], 'cpu')
        self.assertIsNone(result['name'])
        self.assertEqual(result['vram_total_mb'], 0)
        self.assertEqual(result['vram_free_mb'], 0)

    @patch('torch.cuda.is_available')
    @patch('torch.backends.mps.is_available', create=True)
    def test_check_gpu_mps(self, mock_mps_is_available, mock_cuda_is_available):
        mock_cuda_is_available.return_value = False
        mock_mps_is_available.return_value = True

        with patch('builtins.hasattr', return_value=True):
            result = check_gpu()

        self.assertEqual(result['available'], True)
        self.assertEqual(result['device'], 'mps')
        self.assertEqual(result['name'], 'Apple Silicon (MPS)')
        self.assertEqual(result['vram_total_mb'], 0)
        self.assertEqual(result['vram_free_mb'], 0)

    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_properties')
    @patch('torch.cuda.memory_allocated')
    @patch('torch.version')
    def test_check_gpu_cuda(self, mock_version, mock_memory_allocated, mock_get_device_properties, mock_cuda_is_available):
        mock_cuda_is_available.return_value = True

        mock_props = MagicMock()
        mock_props.total_memory = 24 * 1024 * 1024 * 1024 # 24 GB
        mock_props.name = "NVIDIA RTX 5070 Ti"
        mock_props.major = 8
        mock_props.minor = 9
        mock_get_device_properties.return_value = mock_props

        mock_memory_allocated.return_value = 4 * 1024 * 1024 * 1024 # 4 GB

        mock_version.cuda = "12.1"

        result = check_gpu()

        self.assertEqual(result['available'], True)
        self.assertEqual(result['device'], 'cuda')
        self.assertEqual(result['name'], "NVIDIA RTX 5070 Ti")
        self.assertEqual(result['vram_total_mb'], 24 * 1024)
        self.assertEqual(result['vram_free_mb'], 20 * 1024)
        self.assertEqual(result['cuda_version'], "12.1")
        self.assertEqual(result['compute_capability'], "8.9")

    def test_estimate_vram(self):
        # Known model, float16
        self.assertEqual(estimate_vram("medium", "float16"), 5000)

        # Known model, float32
        self.assertEqual(estimate_vram("medium", "float32"), 10000)

        # Another known model, different precision name falls back to float16
        self.assertEqual(estimate_vram("large-v3", "int8"), 10000)

        # Unknown model falls back to large-v3 float16
        self.assertEqual(estimate_vram("unknown", "float16"), 10000)

    def test_check_vram_sufficient_no_gpu(self):
        gpu_info = {"available": False}
        sufficient, msg = check_vram_sufficient("medium", "float16", gpu_info)
        self.assertFalse(sufficient)
        self.assertIn("No GPU acceleration", msg)

    def test_check_vram_sufficient_mps(self):
        gpu_info = {"available": True, "device": "mps"}
        sufficient, msg = check_vram_sufficient("medium", "float16", gpu_info)
        self.assertTrue(sufficient)
        self.assertIn("Apple Silicon MPS", msg)

    def test_check_vram_sufficient_cuda_ok(self):
        gpu_info = {
            "available": True,
            "device": "cuda",
            "vram_total_mb": 8000
        }
        # medium float16 needs 5000
        sufficient, msg = check_vram_sufficient("medium", "float16", gpu_info)
        self.assertTrue(sufficient)
        self.assertIn("VRAM OK", msg)

    def test_check_vram_sufficient_cuda_insufficient(self):
        gpu_info = {
            "available": True,
            "device": "cuda",
            "vram_total_mb": 4000
        }
        # medium float16 needs 5000
        sufficient, msg = check_vram_sufficient("medium", "float16", gpu_info)
        self.assertFalse(sufficient)
        self.assertIn("but GPU has", msg)

if __name__ == '__main__':
    unittest.main()
