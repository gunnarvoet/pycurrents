#!/usr/bin/env python

from pathlib import Path
from pycurrents.adcp.rdiraw import Multiread      # singleping ADCP
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
import logging

_log = logging.getLogger(__file__)

def outside_bounds(upper_bound, lower_bound, beam_data, debug = False):
    if debug:
        _log.debug("in debug")
        above = beam_data > upper_bound
        below = beam_data < lower_bound

        if np.any(above):
            indices = np.argwhere(above)
            for idx in indices:
                val = beam_data[tuple(idx)]
                bound = upper_bound[tuple(idx)]
                _log.debug(f"Above upper bound at {tuple(idx)}: value = {val}, bound = {bound}")

        if np.any(below):
            indices = np.argwhere(below)
            for idx in indices:
                val = beam_data[tuple(idx)]
                bound = lower_bound[tuple(idx)]
                _log.debug(f"Below lower bound at {tuple(idx)}: value = {val}, bound = {bound}")

        return np.any(above) or np.any(below)
    #not debug
    return np.any(beam_data > upper_bound) or np.any(beam_data < lower_bound)

def plot_correlations(title, data, depth, files, debug_mode, threshold):
    # rgbk colors on beams
    fig, axs = plt.subplots(ncols=3, sharey=True)

    for ax , var_name, label in zip(axs, [data.cor, data.amp, data.vel], ["Correlation", "Amplitude", "Velocity"]):
        for i, color in enumerate('rgbk'):
            ax.plot(np.mean(var_name[:,:,i], axis=0), depth, label=f'Beam{i+1}', color=color)
        ax.set_title(label)

    # Plot correlations between beam1 and beam2
    ax.invert_yaxis()
    axs[0].set_ylabel('Depth (m)')

    # get median of beams then get std and check if any are outside std
    correlation_median = np.mean(np.median(data.cor, axis=2), axis=0)
    correltation_stdev = np.mean(np.std(data.cor, axis=2), axis=0)
    amp_median = np.mean(np.median(data.amp, axis=2), axis=0)
    amp_stdev = np.mean(np.std(data.amp, axis=2), axis=0)

    _log.debug("Correlation stdev:", correltation_stdev.shape)
    _log.debug("Correlation median:", correlation_median.shape)
    # Calculate the upper and lower bounds
    number_of_std_devs = 1
    cor_upper_bound = np.maximum(
        correlation_median + correltation_stdev * number_of_std_devs,
        correlation_median + threshold
    )
    cor_lower_bound = np.minimum(
        correlation_median - correltation_stdev * number_of_std_devs,
        correlation_median - threshold
    )
    amp_upper_bound = np.maximum(
        amp_median + amp_stdev * number_of_std_devs,
        amp_median + threshold
    )
    amp_lower_bound = np.minimum(
        amp_median - amp_stdev * number_of_std_devs,
        amp_median - threshold
    )

    fig.suptitle(f'{title} - {files[0]}', fontsize=16)

    axs[0].plot(correlation_median, depth, label='Median', color='grey', linestyle='--')
    axs[0].fill_betweenx(depth, cor_lower_bound, cor_upper_bound, color='lightgrey', alpha=0.5, label=f'Median ± \nmax(Std Dev, {threshold}%)')

    axs[1].plot(amp_median, depth, label='Median', color='grey', linestyle='--')
    axs[1].fill_betweenx(depth, amp_lower_bound, amp_upper_bound, color='lightgrey', alpha=0.5, label=f'Median ± \nmax(Std Dev, {threshold}%)')

    axs[0].legend(title="Beam Number", loc='upper right', bbox_to_anchor=(4.8, 1))
    # turn on grid
    [ax.grid(True) for ax in axs]


    # check for out of bounds corr
    was_out_cor = False
    medians = np.mean(data.cor, axis=0)
    for beam_index_corr in range(4):
        outside_bounds_cor = outside_bounds(cor_upper_bound, cor_lower_bound, medians[:,beam_index_corr])
        if outside_bounds_cor:
            was_out_cor |=  outside_bounds_cor
            break

    medians = np.mean(data.amp, axis=0)
    was_out_amp = False
    for beam_index_amp in range(4):
        outside_bounds_amp = outside_bounds(amp_upper_bound, amp_lower_bound, medians[:,beam_index_amp], debug = debug_mode)
        if outside_bounds_amp:
            was_out_amp |=  outside_bounds_amp
            break

    # subtitles
    subtitle_color = 'red' if was_out_cor else 'green'
    # Add subtitle-like annotation
    fig.text(0.35, 0, f'Outlier Correlation:\nin beam {beam_index_corr+1}' if was_out_cor else 'No Outlier',
         color=subtitle_color,
         ha='right', va="bottom")

    subtitle_color = 'red' if was_out_amp else 'green'
    fig.text(0.6, 0, f'Outlier Amplitude:\nin beam {beam_index_amp+1}' if was_out_amp else 'No Outlier',
         color=subtitle_color,
         ha='right', va="bottom")

    return fig, title


def save_correlation_plots(title, fig, save_file_loc = "."):
    # Ensure the directory exists
    output_dir = save_file_loc
    os.makedirs(output_dir, exist_ok=True)

    # Save the figure
    output_path = os.path.join(output_dir, f"testcase_{title}.png")

    fig.savefig(output_path,  bbox_inches='tight')
    print(f"Figure saved to {output_path}")


def read_raw(files):
    # Use Multiread to read the file content
    out_files = [str(p) for p in files]
    M = Multiread(out_files, 'os')
    data = M.read()

    M.pingtypes
    data=M.read()

    depth = data.dep

    print('dday range:', data.dday.min(), data.dday.max())

    return data, depth


def plot_beam_cor_amp_vel(input_raw_dir, save, save_file_loc, allow_symbolic_links, title, debug_mode, threshold = 25):
    """
    Creates a subplot 3x1 of [Correlation, Amplitude, Velocity].

    Parameters:
    ----------
    input_raw_dir : str or Path
        Path to the directory containing .raw input files.
    save : bool
        If True, saves the processed output to disk.
    save_file_loc : str or Path
        Path to save the output file (used only if save is True).
    allow_symbolic_links : bool
        If True, symbolic links in input_raw_dir are followed; otherwise, they are ignored.
    title : str
        Title used for labeling outputs (e.g., plots, saved files).
    debug_mode : bool
        If True, enables additional debug output and logging.

    Returns:
    -------
    None
    """
    if save and not save_file_loc:
        save_file_loc = '.'

    # Current directory
    base_path = Path(input_raw_dir)

    # List all .raw files without following symlinks
    if allow_symbolic_links:
        raw_files = [p for p in base_path.rglob('*.raw') if p.name.endswith('.raw') and p.suffix == '.raw']
    else:
        raw_files = [
            p for p in base_path.rglob('*.raw')
            if not p.is_symlink() and p.name.endswith('.raw') and p.suffix == '.raw'
        ]


    data, depth = read_raw(raw_files)

    fig, title = plot_correlations(title, data, depth, raw_files, debug_mode, threshold)

    if save:
        save_correlation_plots(title, fig, save_file_loc)
    else:
        plt.tight_layout()
        plt.subplots_adjust(right=.75)  # Increase right margin to fit legend
        plt.show()

    plt.close(fig)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load and save raw dir")
    parser.add_argument('--input', '-i', type=str, required=True, help="Path to input .raw files")
    parser.add_argument('--output', '-o', type=str, help="Path to save")
    parser.add_argument('--save', default=False, action='store_true', help="If set, save the output array")
    parser.add_argument('--allow_symbolic_links', action='store_true', help="by default dont follow sym links")
    parser.add_argument('--title', '-t', type=str, help="Optional title; defaults to last folder in input path")
    parser.add_argument('--debug', '-d', action='store_true', help="set debug mode [default off]")

    args = parser.parse_args()

    input_path = Path(args.input).resolve()

    # If no title is provided, use the last folder in the input path
    if args.title:
        title = args.title
    else:
        # Use parent folder if input is a file, or the folder itself if it's a directory
        title = input_path.name if input_path.is_dir() else input_path.parent.name

    if args.output:
        args.save = True

    plot_beam_cor_amp_vel(args.input, args.save, args.output, args.allow_symbolic_links, title, args.debug)
