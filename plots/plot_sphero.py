import numpy as np

import common

runs = []
runs += common.load_runs('scores/sphero_dreamer.json')
runs += common.load_runs('scores/sphero_drqv2.json')

bins = 30
steps_per_min = 77
total_steps = 130 * steps_per_min

labels = {
    'dreamer': 'Dreamer',
    'drqv2': 'DrQv2',
}

borders = np.linspace(0, total_steps, bins)
for run in runs:
  xs, ys = common.binning(run['xs'], run['ys'], borders, np.nanmean)
  _, area = common.binning(run['xs'], run['ys'], borders, np.nanstd)
  # xs, ys, area = xs[1:], ys[1:], area[1:]
  run.update({'xs': xs, 'ys': ys, 'area': area})

fig, axes = common.plots(1, cols=1, size=(2.1, 2))

ax = axes[0]
ax.set_title('Sphero Navigation', fontsize='medium')
ax.set_xlabel('Minutes')
ax.set_ylabel('Avg Dist to Goal')
for index, run in enumerate(runs):
  label = labels[run['method']]
  print(f"Plotting {label}")
  x, m, s = run['xs'], run['ys'], run['area']
  x = x / steps_per_min
  m *= -1
  common.curve(
      ax, x, m, m - s, m + s,
      label=label,
      order=index,
  )

ax.legend(
    loc='upper right', fancybox=False, edgecolor='#ffffff',
    handlelength=1.2, handletextpad=0.5,
    borderaxespad=0.15, fontsize='small')

ax.set_xlim(0, total_steps / steps_per_min * 1.05)
ax.set_ylim(0.05, 0.95)
ax.set_yticks([0.1, 0.3, 0.5, 0.7, 0.9])

fig.tight_layout()

common.save(fig, 'figs/sphero.png', dpi=300)
common.save(fig, 'figs/sphero.pdf')

