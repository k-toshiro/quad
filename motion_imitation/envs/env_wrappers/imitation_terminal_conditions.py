"""Contains the terminal conditions for imitation task."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np

from utilities import pose3d
from utilities import motion_util
from pybullet_utils import transformations


def imitation_terminal_condition(env,
                                 dist_fail_threshold=1.0,
                                 rot_fail_threshold=0.5 * np.pi):
  """A terminal condition for motion imitation task.

  Args:
    env: An instance of MinitaurGymEnv
    dist_fail_threshold: Max distance the simulated character's root is allowed
      to drift from the reference motion before the episode terminates.
    rot_fail_threshold: Max rotational difference between simulated character's
      root and the reference motion's root before the episode terminates.

  Returns:
    A boolean indicating if episode is over.
  """

  task = env.task

  motion_over = task.is_motion_over()
  foot_links = env.robot.GetFootLinkIDs()
  ground = env.get_ground()

  contact_fall = False
  # sometimes the robot can be initialized with some ground penetration
  # so do not check for contacts until after the first env step.
  if env.env_step_counter > 0:
    robot_ground_contacts = env.pybullet_client.getContactPoints(
        bodyA=env.robot.quadruped, bodyB=ground)

    for contact in robot_ground_contacts:
      if contact[3] not in foot_links:
        contact_fall = True
        break

  root_pos_ref = task.get_ref_base_position()
  root_rot_ref = task.get_ref_base_rotation()
  root_pos_robot = env.robot.GetBasePosition()
  root_rot_robot = env.robot.GetBaseOrientation()

  root_pos_diff = np.array(root_pos_ref) - np.array(root_pos_robot)
  root_pos_fail = (
      root_pos_diff.dot(root_pos_diff) >
      dist_fail_threshold * dist_fail_threshold)

  root_rot_diff = transformations.quaternion_multiply(
      np.array(root_rot_ref),
      transformations.quaternion_conjugate(np.array(root_rot_robot)))
  root_rot_diff /= np.linalg.norm(root_rot_diff)
  _, root_rot_diff_angle = pose3d.QuaternionToAxisAngle(
      root_rot_diff)
  root_rot_diff_angle = motion_util.normalize_rotation_angle(
      root_rot_diff_angle)
  root_rot_fail = (np.abs(root_rot_diff_angle) > rot_fail_threshold)

  done = motion_over \
      or contact_fall \
      or root_pos_fail \
      or root_rot_fail

  return done
