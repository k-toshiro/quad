# vim: set textwidth=0 wrapmargin=0 nowrap :

import datetime

from absl import app
from xmanager import xm
from xmanager import xm_abc
from xmanager.contrib.internal import tensorboard


def launch(name, configs, seeds=1):

  time = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S').lower()
  exid = f't{time}-daydreaming-{name}'.replace('_', '-')
  basedir = f'/gcs/xcloud-shared/daydreaming/{exid}'

  flags_list = []
  for method, config in configs.items():
    for seed in range(seeds):
      logdir = f'{basedir}/{method}/{seed}'
      flags_list.append({**config, 'logdir': logdir, 'seed': seed})

  print(f'Launching {exid} with {len(flags_list)} runs.')

  for flags_dict in flags_list:
    for key, value in flags_dict.items():
      if isinstance(value, (list, tuple)):
        value = ','.join([str(x) for x in value])
      value = str(value)
      flags_dict[key] = value

  with xm_abc.create_experiment(exid) as exp:
    tensorboard.add_tensorboard_borg(
        exp, basedir.replace('/gcs/', '/bigstore/'))
    executor = xm_abc.executors.Gcp(xm.JobRequirements(cpu=5, v100=1))
    executable, = exp.package([xm.dockerfile_container(
        executor.Spec(), '.', 'Dockerfile',
        args='python3 embodied/agents/dreamerv3/train.py'.split())])
    for flags_dict in flags_list:
      exp.add(xm.Job(executable, executor, args=flags_dict))


def main(argv):

  # launch('daydreaming_initial', {
  #     'dreamerv3': {'configs': ['a1']},
  # }, seeds=3)

  # launch('daydream_actent', {
  #     'actent01': {'configs': ['a1'], 'actent.target': 0.1},
  #     'actent02': {'configs': ['a1'], 'actent.target': 0.2},
  #     'actent03': {'configs': ['a1'], 'actent.target': 0.3},
  #     'actent04': {'configs': ['a1'], 'actent.target': 0.4},
  #     'actent05': {'configs': ['a1'], 'actent.target': 0.5},
  # }, seeds=3)

  # launch('daydream_train', {
  #     'train2every1': {'configs': ['a1'], 'train.train_every': 1, 'train.train_steps': 2},
  #     'train1every1': {'configs': ['a1'], 'train.train_every': 1},
  #     'train1every2': {'configs': ['a1'], 'train.train_every': 2},
  #     'train1every4': {'configs': ['a1'], 'train.train_every': 4},
  #     'noresets': {'configs': ['a1'], 'env.resets': False},
  # }, seeds=3)

  # launch('daydream_noreset', {
  #     'resets': {'configs': ['a1'], 'env.resets': True},
  #     'noresets': {'configs': ['a1'], 'env.resets': False},
  # }, seeds=3)

  # launch('daydream_every', {
  #     'every1': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 1, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'every2': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'every4': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 4, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'every8': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 8, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'every16': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 16, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'every32': {'configs': ['a1'], 'env.resets': False, 'env.repeat': 50, 'train.train_every': 32, 'replay_fixed.length': 32, 'batch_size': 64},
  # }, seeds=2)

  # launch('daydream_faster', {
  #     'batch64x32_every2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every3': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 3, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every3': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 3, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every4_repeat25': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 4, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every4_repeat25': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 4, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every2_repeat100': {'configs': ['a1'], 'env.repeat': 100, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every2_repeat100': {'configs': ['a1'], 'env.repeat': 100, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 128},
  # }, seeds=2)

  # launch('daydream_faster', {
  #     'batch64x32_every2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every3': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 3, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every3': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 3, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every4_repeat25': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 4, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every4_repeat25': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 4, 'replay_fixed.length': 32, 'batch_size': 128},
  #     'batch64x32_every2_repeat100': {'configs': ['a1'], 'env.repeat': 100, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 64},
  #     'batch128x32_every2_repeat100': {'configs': ['a1'], 'env.repeat': 100, 'train.train_every': 2, 'replay_fixed.length': 32, 'batch_size': 128},
  # }, seeds=2)

  # launch('daydream_repeat', {
  #     'every1': {'configs': ['a1'], 'train.train_every': 1},
  #     'every2': {'configs': ['a1'], 'train.train_every': 2},
  #     'every3': {'configs': ['a1'], 'train.train_every': 3},
  #     'every4': {'configs': ['a1'], 'train.train_every': 4},
  # }, seeds=3)

  # launch('daydream_repeat', {
  #     'repeat12_every8': {'configs': ['a1'], 'env.repeat': 12, 'train.train_every': 8},
  #     'repeat25_every4': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 4},
  #     'repeat50_every2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2},
  #     'repeat100_every1': {'configs': ['a1'], 'env.repeat': 100, 'train.train_every': 1},
  # }, seeds=3)

  # launch('daydream_model', {
  #     'current': {'configs': ['a1']},
  #     'layers2': {'configs': ['a1'], r'.*\.layers': 2},
  #     'units128': {'configs': ['a1'], r'.*\.units': 128},
  #     'nonorm': {'configs': ['a1'], r'.*\.norm': 'none'},
  #     'length16': {'configs': ['a1'], 'replay_fixed.length': 16},
  #     'imag8': {'configs': ['a1'], 'imag_horizon': 8},
  #     'rssm128': {'configs': ['a1'], 'rssm.deter': 128, 'rssm.units': 128},
  # }, seeds=3)

  launch('daydream_tuning', {
      'current': {'configs': ['a1']},
      'repeat25_train8': {'configs': ['a1'], 'env.repeat': 25, 'train.train_every': 8},
      'repeat50_train2': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 2},
      'repeat50_train4': {'configs': ['a1'], 'env.repeat': 50, 'train.train_every': 4},
      'layers2': {'configs': ['a1'], r'.*\.layers': 2},
      'lrs3em4': {'configs': ['a1'], r'.*\.lr': 3e-4},
      'batch64': {'configs': ['a1'], 'batch_size': 64},
      'length16': {'configs': ['a1'], 'replay_fixed.length': 16},
  }, seeds=5)


if __name__ == '__main__':
  app.run(main)
