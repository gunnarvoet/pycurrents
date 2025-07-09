from pycurrents.scripts.monitor_xpings import make_axes
import matplotlib

matplotlib.use('Agg')  # Use the non-interactive backend for tests

def test_monitor_pings():

    fig, _ = matplotlib.pyplot.subplots()
    qfigs = make_axes(fig)

    assert qfigs, "failed to make qfigs"
