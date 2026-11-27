import subprocess
import sys

CHECK = """
import matplotlib as mpl
before = dict(mpl.rcParams)
import uplift.budget, uplift.learners, uplift.plots, uplift.selection
changed = sorted(k for k, v in mpl.rcParams.items() if before[k] != v)
print(changed)
"""


def test_plot_modules_leave_matplotlib_style_unchanged():
    out = subprocess.run(
        [sys.executable, "-c", CHECK], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip().splitlines()[-1] == "[]"
