import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'examples' / 'benchmark.py'


def launch(*flags):
    env = os.environ.copy()
    env.pop('IQGRAM_API_ID', None)
    env.pop('IQGRAM_API_HASH', None)
    return subprocess.run([sys.executable, str(SCRIPT), '--chat', 'me', '--message', '7552', *flags],
                          cwd=ROOT, env=env, text=True, capture_output=True)


def test_benchmark_accepts_pipeline_depth_two():
    result = launch('--upload-pipeline-depth', '2')
    assert result.returncode != 2
    assert 'Set IQGRAM_API_ID' in result.stderr


def test_benchmark_rejects_pipeline_depth_out_of_range():
    result = launch('--upload-pipeline-depth', '5')
    assert result.returncode == 2
    assert 'between 1 and 4' in result.stderr


def test_help_describes_experimental_pipeline():
    result = launch('--help')
    assert result.returncode == 0
    assert '--upload-pipeline-depth' in result.stdout
