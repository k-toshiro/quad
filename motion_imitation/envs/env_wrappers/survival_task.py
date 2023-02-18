"""A simple locomotion task and termination condition."""
class SurvivalTask(object):
  """Default empy task."""
  def __init__(self):
    """Initializes the task."""
    self._draw_ref_model_alpha = 1.
    self._ref_model = -1

  def __call__(self, env):
    return self.reward(env)

  def reset(self, env):
    """Resets the internal state of the task."""
    self._env = env

  def update(self, env):
    """Updates the internal state of the task."""
    del env

  def done(self, env):
    """Checks if the episode is over."""
    del env
    return False

  def reward(self, env):
    """Get the reward without side effects."""
    del env
    return 1
