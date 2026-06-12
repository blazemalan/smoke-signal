import unittest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import os

from smoke_signal.config import (
    get_data_dir,
    load_config,
    get_profile,
    save_config,
    is_setup_complete,
    DEFAULT_CONFIG_PATH,
)

class TestConfig(unittest.TestCase):
    @patch("pathlib.Path.mkdir")
    @patch("platform.system")
    @patch.dict(os.environ, {"SMOKE_SIGNAL_DATA_DIR": "/custom/path"}, clear=True)
    def test_get_data_dir_override(self, mock_system, mock_mkdir):
        self.assertEqual(get_data_dir(), Path("/custom/path"))

    @patch("pathlib.Path.mkdir")
    @patch("platform.system", return_value="Windows")
    @patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local"}, clear=True)
    def test_get_data_dir_windows(self, mock_system, mock_mkdir):
        expected = Path("C:\\Users\\Test\\AppData\\Local") / "SmokeSignal"
        self.assertEqual(get_data_dir(), expected)

    @patch("pathlib.Path.mkdir")
    @patch("platform.system", return_value="Windows")
    @patch.dict(os.environ, {}, clear=True)
    def test_get_data_dir_windows_no_localappdata(self, mock_system, mock_mkdir):
        expected = Path.home() / "AppData" / "Local" / "SmokeSignal"
        self.assertEqual(get_data_dir(), expected)

    @patch("pathlib.Path.mkdir")
    @patch("platform.system", return_value="Darwin")
    @patch.dict(os.environ, {}, clear=True)
    def test_get_data_dir_darwin(self, mock_system, mock_mkdir):
        expected = Path.home() / "Library" / "Application Support" / "SmokeSignal"
        self.assertEqual(get_data_dir(), expected)

    @patch("pathlib.Path.mkdir")
    @patch("platform.system", return_value="Linux")
    @patch.dict(os.environ, {}, clear=True)
    def test_get_data_dir_linux(self, mock_system, mock_mkdir):
        expected = Path.home() / ".local" / "share" / "smoke-signal"
        self.assertEqual(get_data_dir(), expected)

    def test_load_config_not_exists(self):
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False

        config = load_config(mock_path)
        self.assertEqual(config, {"defaults": {}, "profiles": {}})

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_config_exists(self, mock_safe_load, mock_file):
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_safe_load.return_value = {"defaults": {"model": "tiny"}, "profiles": {}}

        config = load_config(mock_path)
        self.assertEqual(config, {"defaults": {"model": "tiny"}, "profiles": {}})
        mock_file.assert_called_once()
        self.assertEqual(mock_file.call_args[0][0], mock_path)

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_config_exists_but_empty(self, mock_safe_load, mock_file):
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True

        mock_safe_load.return_value = None

        config = load_config(mock_path)
        self.assertEqual(config, {"defaults": {}, "profiles": {}})

    def test_get_profile(self):
        config = {
            "defaults": {"model": "tiny", "language": "en"},
            "profiles": {
                "fast": {"model": "tiny"},
                "accurate": {"model": "large", "compute_type": "float32"}
            }
        }

        fast_profile = get_profile(config, "fast")
        self.assertEqual(fast_profile, {"model": "tiny", "language": "en"})

        accurate_profile = get_profile(config, "accurate")
        self.assertEqual(accurate_profile, {"model": "large", "language": "en", "compute_type": "float32"})

        missing_profile = get_profile(config, "missing")
        self.assertEqual(missing_profile, {"model": "tiny", "language": "en"})

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.dump")
    def test_save_config(self, mock_yaml_dump, mock_file):
        mock_path = MagicMock(spec=Path)
        config = {"defaults": {"model": "tiny"}}

        save_config(config, mock_path)

        mock_file.assert_called_once_with(mock_path, "w", encoding="utf-8")
        mock_yaml_dump.assert_called_once_with(config, mock_file(), default_flow_style=False, sort_keys=False)

    @patch("smoke_signal.config.load_env")
    @patch("pathlib.Path.exists")
    @patch.dict(os.environ, {"HF_TOKEN": "test_token"}, clear=True)
    def test_is_setup_complete_true(self, mock_exists, mock_load_env):
        mock_exists.return_value = True
        self.assertTrue(is_setup_complete())
        mock_load_env.assert_called_once()

    @patch("smoke_signal.config.load_env")
    @patch("pathlib.Path.exists")
    @patch.dict(os.environ, {}, clear=True)
    def test_is_setup_complete_no_token(self, mock_exists, mock_load_env):
        self.assertFalse(is_setup_complete())

    @patch("smoke_signal.config.load_env")
    @patch("pathlib.Path.exists")
    @patch.dict(os.environ, {"HF_TOKEN": "test_token"}, clear=True)
    def test_is_setup_complete_no_config(self, mock_exists, mock_load_env):
        mock_exists.return_value = False
        self.assertFalse(is_setup_complete())

if __name__ == "__main__":
    unittest.main()
