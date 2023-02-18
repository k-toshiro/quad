import os
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(os.path.dirname(currentdir))
os.sys.path.insert(0, parentdir)

import argparse
import numpy as np
import os
import random
import time

from motion_imitation.envs import env_builder as env_builder
from motion_imitation.robots import robot_config

from motion_imitation.robots import laikago

def test(env):
  o = env.reset()
  while 1:
    a = laikago.INIT_MOTOR_ANGLES
    o, r, done, info = env.step(a)
    if done:
        o = env.reset()
  return

def main():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument("--seed", dest="seed", type=int, default=None)
  arg_parser.add_argument("--visualize", dest="visualize", action="store_true", default=True)

  args = arg_parser.parse_args()
 
  env = env_builder.build_laikago_env( motor_control_mode = robot_config.MotorControlMode.POSITION, enable_rendering=args.visualize)
  
  test(env=env)
  
  return

if __name__ == '__main__':
  main()
