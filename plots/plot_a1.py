import numpy as np

import common

runs = []
runs += common.load_runs('scores/a1_dreamer.json')
runs += common.load_runs('scores/a1_sac.json')

bins = 40
steps_per_min = 20 * 60
total_steps = 0.985 * 60 * steps_per_min

labels = {
    'dreamer': 'Dreamer',
    'sac': 'SAC',
}

borders = np.linspace(0, total_steps, bins)
for run in runs:
  xs, ys = common.binning(run['xs'], run['ys'], borders, np.nanmean)
  _, area = common.binning(run['xs'], run['ys'], borders, np.nanstd)
  run.update({'xs': xs, 'ys': ys, 'area': area})

fig, axes = common.plots(1, cols=1, size=(2.1, 2))

ax = axes[0]
ax.set_title('A1 Quadruped Walking', fontsize='medium')
ax.set_xlabel('Minutes')
ax.set_ylabel('Avg Reward')
for index, run in enumerate(runs):
  label = labels[run['method']]
  print(f"Plotting {label}")
  x, m, s = run['xs'], run['ys'], run['area']
  x = x / steps_per_min
  common.curve(
      ax, x, m, m - s, m + s,
      label=label,
      order=index,
  )

ax.scatter(
    [0.5, 13.4, 30.3, 42.3, 51.5],
    [5, 5.1, 5.4, 6.1, 8.3],
    s=10, c='#1f77b4', zorder=100 - 0)

ax.scatter(
    [1.0, 42.5, 53.1],
    [5, 6.4, 6.5],
    s=10, c='#ff7f0e', zorder=100 - 1)

ax.legend(
    loc='upper left', fancybox=False, edgecolor='#ffffff',
    handlelength=1.2, handletextpad=0.5,
    borderaxespad=0.15, fontsize='small')

ax.set_ylim(4.5, 11.8)
ax.set_yticks([5, 7, 9, 11])

fig.tight_layout()

common.save(fig, 'figs/a1.png', dpi=300)
common.save(fig, 'figs/a1.pdf')
