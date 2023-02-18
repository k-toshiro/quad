import gzip
import json
import pathlib
import subprocess
import warnings

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


COLORS = {
    'discrete': (
        '#377eb8', '#4daf4a', '#984ea3', '#e41a1c', '#ff7f00', '#a65628',
        '#f781bf', '#888888', '#a6cee3', '#b2df8a', '#cab2d6', '#fb9a99'),
    'contrast': (
        '#0022ff', '#33aa00', '#ff0011', '#ddaa00', '#cc44dd', '#0088aa',
        '#001177', '#117700', '#990022', '#885500', '#553366', '#006666'),
    'gradient': (
        '#fde725', '#a0da39', '#4ac16d', '#1fa187', '#277f8e', '#365c8d',
        '#46327e', '#440154'),
    'grays': (
        '#222222', '#666666', '#aaaaaa', '#cccccc'),
}


def binning(xs, ys, borders, reducer=np.nanmean, fill='nan'):
  xs = xs if isinstance(xs, np.ndarray) else np.array(xs)
  ys = ys if isinstance(ys, np.ndarray) else np.array(ys)
  order = np.argsort(xs)
  xs, ys = xs[order], ys[order]
  binned = []
  for start, stop in zip(borders[:-1], borders[1:]):
    left = (xs <= start).sum()
    right = (xs <= stop).sum()
    if left < right:
      value = reduce(ys[left:right], reducer)
    elif binned:
      value = {'nan': np.nan, 'last': binned[-1]}[fill]
    else:
      value = np.nan
    binned.append(value)
  return borders[1:], np.array(binned)


def curve(
    ax, domain, values, low=None, high=None, label=None, order=0, **kwargs):
  finite = np.isfinite(values)
  ax.plot(
      domain[finite], values[finite],
      label=label, zorder=100 - order, **kwargs)
  if low is not None:
    ax.fill_between(
        domain[finite], low[finite], high[finite],
        zorder=10 - order, alpha=0.2, lw=0, **kwargs)


def legend(fig, mapping=None, adjust=False, **kwargs):
  options = dict(
      fontsize='medium', numpoints=1, labelspacing=0, columnspacing=1.2,
      handlelength=1.5, handletextpad=0.5, ncol=4, loc='lower center')
  options.update(kwargs)
  # Find all labels and remove duplicates.
  entries = {}
  for ax in fig.axes:
    for handle, label in zip(*ax.get_legend_handles_labels()):
      if mapping and label in mapping:
        label = mapping[label]
      entries[label] = handle
  leg = fig.legend(entries.values(), entries.keys(), **options)
  leg.get_frame().set_edgecolor('white')
  if adjust is not False:
    pad = adjust if isinstance(adjust, (int, float)) else 0.5
    extent = leg.get_window_extent(fig.canvas.get_renderer())
    extent = extent.transformed(fig.transFigure.inverted())
    yloc, xloc = options['loc'].split()
    y0 = dict(lower=extent.y1, center=0, upper=0)[yloc]
    y1 = dict(lower=1, center=1, upper=extent.y0)[yloc]
    x0 = dict(left=extent.x1, center=0, right=0)[xloc]
    x1 = dict(left=1, center=1, right=extent.x0)[xloc]
    fig.tight_layout(rect=[x0, y0, x1, y1], h_pad=pad, w_pad=pad)


def load_runs(filename):
  filename = pathlib.Path(filename)
  runs = []
  if filename.suffix == '.gz':
    with gzip.open(filename) as f:
      runs += json.load(f)
  elif filename.suffix == '.json':
    with open(filename, 'r') as f:
      runs += json.load(f)
  elif filename.suffix == '.npz':
    data = np.load(filename)
    for key in data.keys():
      task, method, seed = key.split('-')
      values = data[key]
      runs.append({
          'task': task, 'method': method, 'seed': seed,
          'xs': values[:, 0].tolist(),
          'ys': values[:, 1].tolist()})
  return runs


def load(filenames, bins, limit=None):
  filenames = [pathlib.Path(x).expanduser() for x in filenames]
  runs = []
  for inpath in filenames:
    runs += load_runs(inpath)
  for run in runs:
    if run['task'] == 'atari_jamesbond':
      run['task'] = 'atari_james_bond'
    if run['task'] == 'dmc_ball_in_cup_catch':
      run['task'] = 'dmc_cup_catch'
  tasks = sorted(set(run['task'] for run in runs))
  methods = sorted(set(run['method'] for run in runs))
  seeds = sorted(set(run['seed'] for run in runs))
  print(f'Tasks ({len(tasks)}): {", ".join(tasks)}')
  print(f'Methods ({len(methods)}): {", ".join(methods)}')
  print(f'Seed ({len(seeds)}): {", ".join(seeds)}')
  lo = bins * np.floor(min(min(run['xs']) for run in runs) / bins)
  hi = bins * np.ceil(max(max(run['xs']) for run in runs) / bins)
  borders = np.arange(lo, min(hi, limit), bins)
  domain = borders[1:]
  scores = np.full(
      (len(tasks), len(methods), len(seeds), len(domain)), np.nan)
  for run in runs:
    i = tasks.index(run['task'])
    j = methods.index(run['method'])
    k = seeds.index(run['seed'])
    scores[i, j, k, :] = binning(run['xs'], run['ys'], borders)[1]
  return domain, scores, tasks, methods, seeds


def plots(
    amount, cols=4, size=(2, 2.3), xticks=4, yticks=5, grid=(1, 1), **kwargs):
  rows = int(np.ceil(amount / cols))
  size = (cols * size[0], rows * size[1])
  fig, axes = plt.subplots(rows, cols, figsize=size, squeeze=False, **kwargs)
  axes = axes.flatten()
  for ax in axes:
    ax.xaxis.set_major_locator(ticker.MaxNLocator(xticks))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(yticks))
    if grid:
      grid = (grid, grid) if not hasattr(grid, '__len__') else grid
      ax.grid(which='both', color='#eeeeee', zorder=0)
      ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(int(grid[0])))
      ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(int(grid[1])))
      ax.tick_params(which='minor', length=0)
  for ax in axes[amount:]:
    ax.axis('off')
  return fig, axes


def save(fig, filename, **kwargs):
  filename = pathlib.Path(filename).expanduser()
  filename.parent.mkdir(parents=True, exist_ok=True)
  fig.savefig(filename, **kwargs)
  print('Saved', filename)
  if filename.suffix == '.pdf':
    try:
      subprocess.call(['pdfcrop', str(filename), str(filename)])
    except FileNotFoundError:
      print('Install LaTeX to crop PDF outputs.')


def reduce(values, reducer=np.nanmean, *args, **kwargs):
  with warnings.catch_warnings():  # Buckets can be empty.
    warnings.simplefilter('ignore', category=RuntimeWarning)
    return reducer(values, *args, **kwargs)
