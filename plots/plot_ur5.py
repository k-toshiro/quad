import numpy as np

import common

runs = []
runs += common.load_runs('scores/ur5_dreamer.json')
runs += common.load_runs('scores/ur5_rainbow.json')
runs += common.load_runs('scores/ur5_ppo.json')

labels = {
    'dreamer': 'Dreamer',
    'rainbow': 'Rainbow',
    'ppo': 'PPO',
}

bins = 35
steps_per_hour = 4083
episode_length = 100
success_reward = 11
total_steps = 8 * steps_per_hour

borders = np.linspace(0, total_steps, bins)
for run in runs:
  xs, ys = common.binning(run['xs'], run['ys'], borders, np.nanmean)
  _, area = common.binning(run['xs'], run['ys'], borders, np.nanstd)
  run.update({'xs': xs, 'ys': ys, 'area': area})

fig, axes = common.plots(1, cols=1, size=(2.1, 2))

ax = axes[0]
ax.set_title('UR5 Visual Pick Place', fontsize='medium')
ax.set_xlabel('Hours')
ax.set_ylabel('Objects / Minute')
for index, run in enumerate(runs):
  print(f"Plotting {run['method']}")
  x, m, s = run['xs'], run['ys'], run['area']
  x = x / steps_per_hour
  m = m / success_reward / episode_length * 60
  s = s / success_reward / episode_length * 60
  common.curve(
      ax, x, m, m - s, m + s,
      label=labels[run['method']],
      order=index,
  )

human_mean = 53
human_std = 27
m = human_mean / success_reward / episode_length * 60
print(m)
ax.axhline(m, ls='--', c='#666666')
ax.text(5.5, m + 0.2, 'Human', c='#666666', fontsize='small')

ax.set_ylim(-0.2, 4)
ax.set_xticks([0, 2, 4, 6, 8])

ax.legend(
    loc='center left', fancybox=False, edgecolor='#ffffff',
    handlelength=1.2, handletextpad=0.5,
    borderpad=0.18,
    borderaxespad=0.15, fontsize='small')

fig.tight_layout()

common.save(fig, 'figs/ur5.png', dpi=300)
common.save(fig, 'figs/ur5.pdf')

