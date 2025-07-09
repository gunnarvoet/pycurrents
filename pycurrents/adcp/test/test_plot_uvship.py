from unittest.mock import patch, MagicMock
from pycurrents.adcp.plot_uvship import plot_uvship, main

import matplotlib.pyplot as plt
import pytest
import numpy as np


@pytest.fixture
def mock_loadtxt():
    with patch('pycurrents.adcp.plot_uvship.loadtxt_') as mock:
        yield mock

@pytest.fixture
def mock_plt():
    with patch('pycurrents.adcp.plot_uvship.plt') as mock:
        yield mock

@pytest.fixture
def mock_plot_uvship():
    with patch('pycurrents.adcp.plot_uvship.plot_uvship') as mock:
        yield mock

@pytest.fixture
def mock_savepngs():
    with patch('pycurrents.adcp.plot_uvship.savepngs') as mock:
        yield mock

def test_plot_uvship(mock_plt, mock_loadtxt):
    # Mock data to simulate the input file
    mock_loadtxt.return_value = (
        np.array([1, 2, 3]),  # dday
        np.array([0.5, 0.6, 0.7]),  # usma
        np.array([0.4, 0.5, 0.6]),  # vsma
        np.array([0.6, 0.7, 0.8]),  # us
        np.array([0.5, 0.6, 0.7]),  # vs
        np.array([10, 20, 30]),  # lon
        np.array([40, 50, 60]),  # lat
        np.array([3, 4, 5])  # N
    )

    # Configure the mock to return a tuple of mock objects
    mock_plt.subplots.return_value = (plt.figure(), MagicMock())

    # Call the function
    fig = plot_uvship("mock_file.txt", maxshipspeed=6)

    # Assertions
    mock_loadtxt.assert_called_once_with("mock_file.txt", unpack=True)
    assert isinstance(fig, plt.Figure)
    assert mock_plt.subplots.call_count == 1

@patch('sys.argv', ['plot_uvship.py', 'mock_file.txt', '--maxspeed=5', '--noshow', '-o', 'output'])
def test_main_with_options(mock_plt, mock_savepngs, mock_plot_uvship):
    # Mock the figure returned by plot_uvship
    mock_fig = MagicMock()
    mock_plot_uvship.return_value = mock_fig

    main()

    # Assertions
    mock_plot_uvship.assert_called_once_with('mock_file.txt', 5.0)
    mock_savepngs.assert_called_once_with('output', dpi=72, fig=mock_fig)
    mock_plt.show.assert_not_called()

@patch('sys.argv', ['plot_uvship.py', 'mock_file.txt'])
def test_main_default_options(mock_plt, mock_plot_uvship):
    # Mock the figure returned by plot_uvship
    mock_fig = MagicMock()
    mock_plot_uvship.return_value = mock_fig

    main()

    # Assertions
    mock_plot_uvship.assert_called_once_with('mock_file.txt', 6.5)
    mock_plt.show.assert_called_once()

@patch('sys.argv', ['plot_uvship.py'])
def test_main_no_arguments():
    with pytest.raises(SystemExit):
        main()