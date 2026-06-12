import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from smoke_signal.audio import (
    validate_audio_file,
    get_audio_duration,
    preprocess_audio,
    SUPPORTED_EXTENSIONS
)

class TestAudio(unittest.TestCase):

    @patch('pathlib.Path.exists')
    def test_validate_audio_file_supported(self, mock_exists):
        mock_exists.return_value = True
        # Try all supported extensions
        for ext in SUPPORTED_EXTENSIONS:
            path = Path(f"test_file{ext}")
            # Should not raise an exception
            validate_audio_file(path)

    @patch('pathlib.Path.exists')
    def test_validate_audio_file_unsupported(self, mock_exists):
        mock_exists.return_value = True
        path = Path("test_file.txt")
        with self.assertRaises(ValueError) as context:
            validate_audio_file(path)
        self.assertIn("Unsupported audio format: .txt", str(context.exception))

    @patch('pathlib.Path.exists')
    def test_validate_audio_file_missing(self, mock_exists):
        mock_exists.return_value = False
        path = Path("test_file.wav")
        with self.assertRaises(FileNotFoundError) as context:
            validate_audio_file(path)
        self.assertIn("Audio file not found: test_file.wav", str(context.exception))

    @patch('smoke_signal.audio.subprocess.run')
    def test_get_audio_duration_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "12.34\n"
        mock_run.return_value = mock_result

        path = Path("test_file.wav")
        duration = get_audio_duration(path)

        self.assertEqual(duration, 12.34)
        mock_run.assert_called_once_with(
            [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", "test_file.wav",
            ],
            capture_output=True, text=True,
        )

    @patch('smoke_signal.audio.subprocess.run')
    def test_get_audio_duration_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some ffprobe error"
        mock_run.return_value = mock_result

        path = Path("test_file.wav")
        with self.assertRaises(RuntimeError) as context:
            get_audio_duration(path)
        self.assertIn("ffprobe failed: some ffprobe error", str(context.exception))

    @patch('smoke_signal.audio.subprocess.run')
    def test_preprocess_audio_with_output_path(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        input_path = Path("input.m4a")
        output_path = Path("output.wav")

        result_path = preprocess_audio(input_path, output_path)

        self.assertEqual(result_path, output_path)
        mock_run.assert_called_once_with(
            [
                "ffmpeg", "-y", "-i", "input.m4a",
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                "output.wav",
            ],
            capture_output=True, text=True,
        )

    @patch('smoke_signal.audio.tempfile.mktemp')
    @patch('smoke_signal.audio.subprocess.run')
    def test_preprocess_audio_without_output_path(self, mock_run, mock_mktemp):
        mock_mktemp.return_value = "/tmp/temp_audio.wav"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        input_path = Path("input.m4a")

        result_path = preprocess_audio(input_path)

        expected_output_path = Path("/tmp/temp_audio.wav")
        self.assertEqual(result_path, expected_output_path)
        mock_run.assert_called_once_with(
            [
                "ffmpeg", "-y", "-i", "input.m4a",
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                "/tmp/temp_audio.wav",
            ],
            capture_output=True, text=True,
        )

    @patch('smoke_signal.audio.subprocess.run')
    def test_preprocess_audio_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some ffmpeg error"
        mock_run.return_value = mock_result

        input_path = Path("input.m4a")
        output_path = Path("output.wav")

        with self.assertRaises(RuntimeError) as context:
            preprocess_audio(input_path, output_path)
        self.assertIn("ffmpeg conversion failed: some ffmpeg error", str(context.exception))

if __name__ == '__main__':
    unittest.main()
