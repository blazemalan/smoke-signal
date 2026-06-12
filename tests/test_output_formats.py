import json
import unittest
from datetime import datetime

from smoke_signal.models import Segment, TranscriptResult, Word
from smoke_signal.output.structured import format_csv, format_json


class TestOutputFormats(unittest.TestCase):
    def setUp(self):
        self.result = TranscriptResult(
            segments=[
                Segment(
                    text="Hello world.",
                    start=0.0,
                    end=1.5,
                    speaker="SPEAKER_00",
                    words=[Word(text="Hello", start=0.0, end=0.5), Word(text="world.", start=0.6, end=1.5)]
                ),
                Segment(
                    text="How are you?",
                    start=1.6,
                    end=2.5,
                    speaker="SPEAKER_01",
                    words=[Word(text="How", start=1.6, end=1.8), Word(text="are", start=1.9, end=2.1), Word(text="you?", start=2.2, end=2.5)]
                ),
            ],
            speakers=["SPEAKER_00", "SPEAKER_01"],
            language="en",
            duration=2.5,
            model="large-v3",
            pipeline="whisper",
            processing_time=1.0,
            audio_file="test.wav",
            date=datetime(2023, 1, 1, 12, 0, 0),
        )

    def test_format_json(self):
        json_output = format_json(self.result)
        data = json.loads(json_output)

        self.assertEqual(data["language"], "en")
        self.assertEqual(data["model"], "large-v3")
        self.assertEqual(len(data["segments"]), 2)
        self.assertEqual(data["segments"][0]["text"], "Hello world.")
        self.assertEqual(data["segments"][0]["speaker"], "SPEAKER_00")

    def test_format_csv(self):
        csv_output = format_csv(self.result)
        lines = csv_output.strip().split("\r\n")

        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "speaker,start,end,text")
        self.assertEqual(lines[1], "SPEAKER_00,0.000,1.500,Hello world.")
        self.assertEqual(lines[2], "SPEAKER_01,1.600,2.500,How are you?")

if __name__ == "__main__":
    unittest.main()
