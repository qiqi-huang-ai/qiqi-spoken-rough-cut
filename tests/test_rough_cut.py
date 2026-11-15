import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'rough_cut.py'
spec = importlib.util.spec_from_file_location('rough_cut', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PlanTests(unittest.TestCase):
    def test_invalid_ranges_and_pending_reviews(self):
        invalid = [
            {'keep': []},
            {'keep': [{'start': -1, 'end': 2, 'reason': 'bad'}]},
            {'keep': [{'start': 1, 'end': 8, 'reason': 'bad'}]},
            {'keep': [{'start': 1, 'end': float('nan'), 'reason': 'bad'}]},
            {'keep': [{'start': True, 'end': 2, 'reason': 'bad'}]},
            {'keep': [{'start': 1, 'end': 2, 'reason': ''}]},
            {'keep': [{'start': 2, 'end': 4, 'reason': 'a'}, {'start': 3, 'end': 5, 'reason': 'b'}]},
            {'keep': [{'start': 1, 'end': 2, 'reason': 'a'}], 'needs_review': ['不确定']},
        ]
        for plan in invalid:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                m.validate_plan(plan, 7)

    def test_time_map_covers_kept_and_removed(self):
        rows = [{'start': 1, 'end': 3, 'reason': 'a'}, {'start': 5, 'end': 7, 'reason': 'b'}]
        summary, duration = m.report(rows, 8, 'hash')
        self.assertEqual(duration, 4)
        for value in ('0.000–1.000', '3.000–5.000', '7.000–8.000', '2.000–4.000'):
            self.assertIn(value, summary)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class RenderTests(unittest.TestCase):
    def test_audio_video_timing_and_source_unchanged(self):
        self.render_case(True)

    def test_video_without_audio(self):
        self.render_case(False)

    def render_case(self, audio):
        with tempfile.TemporaryDirectory(prefix='rough-cut-test-') as td:
            root = Path(td)
            source = root / '原片 with spaces.mp4'
            output = root / '初剪.mp4'
            cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=25:duration=7']
            if audio:
                cmd += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=7', '-c:a', 'aac']
            cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)]
            subprocess.run(cmd, check=True)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            plan = json.loads((ROOT / 'examples' / 'plan.json').read_text())
            rows = m.validate_plan(plan, 7)
            info = m.probe(source)
            result = m.render(source, info, rows, output, 4)
            self.assertAlmostEqual(result['actual_seconds'], 4, delta=0.1)
            out = m.probe(output)
            self.assertEqual(out['video']['avg_frame_rate'], '25/1')
            self.assertEqual(bool(out['audio']), audio)
            if audio:
                self.assertAlmostEqual(float(out['audio']['duration']), 4, delta=0.1)
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
            # Check actual frame content at the first frame of each kept range.
            def frame(path, at):
                return subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(path),
                    '-frames:v', '1', '-vf', 'scale=16:12', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
            for src_time, out_time in ((0.52, 0), (4.0, 2.0)):
                a, b = frame(source, src_time), frame(output, out_time)
                self.assertLess(sum(abs(x-y) for x,y in zip(a,b))/len(a), 4)
            with self.assertRaises(ValueError):
                m.render(source, info, rows, source, 4)
            with self.assertRaises(ValueError):
                m.render(source, info, rows, output, 4)
            p = root / 'plan.json'
            p.write_text(json.dumps(plan))
            bad = subprocess.run([sys.executable, str(SCRIPT), 'render', '--video', str(source),
                '--plan', str(p), '--output', str(root/'must-not-exist.mp4'), '--approved-sha256', 'wrong'],
                capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse((root/'must-not-exist.mp4').exists())


if __name__ == '__main__':
    unittest.main()
