import dataclasses
import enum
import random
import sys
import time
import traceback
from typing import Any, Dict, Optional, Tuple

import cv2
import dcargs
import numpy as np
import pyrealsense2 as rs
from xarm.wrapper import XArmAPI

import embodied
from embodied.envs.spacemouse import SpaceMouse


class Rate:
    def __init__(self, rate: float):
        self.last = time.time()
        self.rate = rate

    def sleep(self) -> None:
        while self.last + 1.0 / self.rate > time.time():
            time.sleep(0.01)
        self.last = time.time()


class ControlMode(enum.Enum):
    NONE = enum.auto()
    DELTA_XY = enum.auto()
    DELTA_XYZ = enum.auto()

    def control_shape(self) -> Tuple[int, ...]:
        if self == ControlMode.DELTA_XY:
            return (2,)
        if self == ControlMode.DELTA_XYZ:
            return (3,)
        else:
            raise NotImplementedError


@dataclasses.dataclass
class EnvConfig:
    control_mode: ControlMode = ControlMode.DELTA_XY  # The control mode
    max_delta_mm: int = 40  # max displacement for the arm per time step
    control_rate_hz: float = 20
    with_camera: bool = True
    debug_cam_vis: bool = False
    use_xarm: bool = True


# 290 205
# 605 225
# 290 -138
# CUBE_SIZE = 10  # 60
# XYZ_MIN = np.array([290 + CUBE_SIZE, -135 + CUBE_SIZE, 175])
# XYZ_MAX = np.array([600 - CUBE_SIZE, 200 - CUBE_SIZE, 550])
# TABLE_Z = 190

# CUBE_SIZE = 20  # 60
XYZ_MIN = np.array([310, -140, 185])
XYZ_MAX = np.array([575, -77, 550])
TABLE_Z = 200


def control_to_target_coords(
    env_config: EnvConfig, control_action: np.ndarray, curr_pose: np.ndarray
) -> np.ndarray:
    """Convert control action to TCP homogeneous transform.

    Args:
        env_config (1nvConfig): The environment configuration.
        control_action (np.ndarray, shape=self.control_shape()): control_action
        (should be values between -1 and 1, following the dm_control convention)
        curr_pose (np.ndarray, shape=(6, )): the current robot pose

    Returns:
        np.ndarray, shape=(6, ): The target pose.
    """
    target_pose = curr_pose.copy()
    control_action = np.clip(control_action, -1, 1) * env_config.max_delta_mm
    if env_config.control_mode == ControlMode.DELTA_XY:
        assert control_action.shape == (2,)
        target_pose[:2] = target_pose[:2] + control_action
        target_pose[2] = TABLE_Z
    elif env_config.control_mode == ControlMode.DELTA_XYZ:
        target_pose = curr_pose.copy()
        assert control_action.shape == (3,)
        target_pose[:3] = target_pose[:3] + control_action
    else:
        raise NotImplementedError

    target_pose[:3] = np.clip(target_pose[:3], XYZ_MIN, XYZ_MAX)
    return target_pose


class BaseEnv:
    def __init__(self, cfg: EnvConfig):
        self.cfg = cfg
        if cfg.use_xarm:
            self._arm = XArmAPI("192.168.1.233")
            self._arm.set_gripper_position(800)
        else:
            self._arm = None
            if not self.cfg.debug_cam_vis:
                return
        # self._arm.connect()
        self.rate = Rate(cfg.control_rate_hz)

        if self.cfg.with_camera:
            ctx = rs.context()
            devices = ctx.query_devices()
            for dev in devices:
                dev.hardware_reset()
            time.sleep(2)
            self.pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
            config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
            self.pipeline.start(config)
            if self.cfg.debug_cam_vis:
                while True:
                    image = self.get_frames()[0][:, :, ::-1]
                    depth = np.repeat(self.get_frames()[1], 3, -1)
                    cv2.imshow("img", np.concatenate([image, depth], 1))

                    # import matplotlib.pyplot as plt
                    # fig, ax = plt.subplots()
                    # ax.hist(depth.ravel(), bins=100)
                    # plt.show()

                    # image = cv2.applyColorMap(255 - depth, cv2.COLORMAP_VIRIDIS)
                    # cv2.imshow("img", depth)

                    cv2.waitKey(1)
        self.clear_error_states()
        self._reset()
        self._gripper_state_open = True  # open
        self.clear_error_states()

    def __len__(self):
        # Return positive integer for batched envs.
        return 0

    def get_frames(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.cfg.with_camera:
            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            color_image = np.asanyarray(color_frame.get_data())
            depth_frame = frames.get_depth_frame()
            depth_image = np.asanyarray(depth_frame.get_data())
            depth_image = cv2.convertScaleAbs(depth_image, alpha=0.03)
            if self.cfg.debug_cam_vis:
                img_size = (480, 480)
            else:
                img_size = (64, 64)
            image = cv2.resize(color_image, img_size)[:, :, ::-1]
            depth = cv2.resize(depth_image, img_size)[:, :, None]
            # Map depth to used range for our robot setup.
            depth = depth.astype(np.float32) / 255
            nearest = 0.050
            farthest = 0.120
            depth = (depth - nearest) / (farthest - nearest)
            depth = (255 * np.clip(depth, 0, 1)).astype(np.uint8)

        else:
            image = np.zeros((64, 64, 3))
            depth = np.zeros((64, 64, 1))
        return image, depth

    def __del__(self) -> None:
        if self._arm is not None:
            self._arm.disconnect()

    @property
    def act_space(self) -> Dict[str, embodied.Space]:
        return {
            "robot_control": embodied.Space(
                np.float32, self.cfg.control_mode.control_shape(), low=-1, high=1
            ),
            "gripper_control": embodied.Space(np.float32, (), low=-1, high=1),
            "reset": embodied.Space(np.bool),
        }

    @property
    def obs_space(self) -> Dict[str, embodied.Space]:
        return {
            "image": embodied.Space(np.uint8, (64, 64, 3)),
            "depth": embodied.Space(np.uint8, (64, 64, 1)),
            "cartesian_position": embodied.Space(np.float32, (6,)),
            "joint_positions": embodied.Space(np.float32, (7,)),
            "gripper_pos": embodied.Space(np.float32, (1,)),
            "grasped_side": embodied.Space(np.float32, (3,)),
            "reward": embodied.Space(np.float32),
            "is_first": embodied.Space(bool),
            "is_last": embodied.Space(bool),
            "is_terminal": embodied.Space(bool),
        }

    def get_reward(self, curr_obs: Dict[str, Any]) -> float:
        """Provides the enviroment reward.

        A subclass should implement this method.

        Args:
            curr_obs (Dict[str, Any]): Observation dict.

        Returns:
            float: reward
        """
        raise NotImplementedError

    def get_obs(
        self,
        robot_in_safe_state: bool,
        is_first: bool = False,
        reward: Optional[float] = None,
    ) -> Dict[str, Any]:
        color_image, depth_image = self.get_frames()

        # change observations to be within reasonable values
        gripper_pos, servo_angle, cart_pos = self.get_proprio()
        cart_pos = np.array(cart_pos.copy())
        cart_pos[:3] /= 100
        grasped_side_one_hot = {
            Side.OTHER: [1, 0, 0],
            Side.LEFT: [0, 1, 0],
            Side.RIGHT: [0, 0, 1],
        }
        obs = dict(
            image=color_image,
            depth=depth_image,
            cartesian_position=cart_pos,
            joint_positions=servo_angle,
            gripper_pos=np.array(gripper_pos)[None] / 800,
            grasped_side=np.array(grasped_side_one_hot[self.grasped_bin], np.float32),
            is_last=False,
            is_terminal=False,
        )

        if reward is None:
            if robot_in_safe_state:
                obs["reward"] = float(self.get_reward(obs))
            else:
                obs["reward"] = float(0)
        else:
            obs["reward"] = reward

        obs["is_first"] = is_first
        return obs

    def get_proprio(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        while self._arm.get_is_moving():
            time.sleep(0.01)

        code, gripper_pos = self._arm.get_gripper_position()
        while code != 0 or gripper_pos is None:
            print(f"Error code {code} in get_gripper_position(). {gripper_pos}")
            self.clear_error_states()
            code, gripper_pos = self._arm.get_gripper_position()

        code, servo_angle = self._arm.get_servo_angle(is_radian=True)
        while code != 0:
            print(f"Error code {code} in get_servo_angle().")
            self.clear_error_states()
            code, servo_angle = self._arm.get_servo_angle(is_radian=True)

        code, cart_pos = self._arm.get_position(is_radian=True)
        while code != 0:
            print(f"Error code {code} in get_position().")
            self.clear_error_states()
            code, cart_pos = self._arm.get_position(is_radian=True)
        return gripper_pos, servo_angle, cart_pos

    def clear_error_states(self):
        self._arm.clean_error()
        self._arm.motion_enable(True)
        self._arm.set_mode(0)
        self._arm.set_state(state=0)
        self._arm.set_gripper_enable(True)
        self._arm.set_gripper_speed(10000)

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        code, curr_cart_pos = self._arm.get_position()
        assert code == 0

        if action["reset"]:
            if action.get("manual_resume", False):
                return self.get_obs(robot_in_safe_state=True, is_first=True)
            else:
                return self._reset()

        xyzrpy = control_to_target_coords(
            self.cfg, action["robot_control"], curr_cart_pos
        )
        self._arm.set_position(
            x=xyzrpy[0],
            y=xyzrpy[1],
            z=xyzrpy[2],
            roll=xyzrpy[3],
            pitch=xyzrpy[4],
            yaw=xyzrpy[5],
        )

        if action["gripper_control"][0] > -0.5:
            if self._gripper_state_open:
                self._arm.set_gripper_position(0, wait=True)
                time.sleep(0.05)
            self._gripper_state_open = False
        else:
            if not self._gripper_state_open:
                self._arm.set_gripper_position(800, wait=True)
                time.sleep(0.05)
            self._gripper_state_open = True

        self.rate.sleep()
        obs = self.get_obs(
            robot_in_safe_state=True, is_first=False,
        )  # TODO, check safe state

        while np.linalg.norm(xyzrpy - np.array(self.get_proprio()[2])) < 2:
            print("moving")
            time.sleep(0.1)

        if action.get("manual_pause", False):
            self._arm.set_gripper_position(800)

        return obs

    def _reset(self) -> Dict[str, Any]:
        if self.cfg.control_mode is ControlMode.DELTA_XY:
            # av = np.deg2rad([1.4, -2.4, -1.2, 23.5, 4.1, 26, -1.8])
            xyzrpy = [335, 0, 190, -180, 0, 0]
        else:
            # av = np.deg2rad([1.2, -23.4, -1.5, 32.6, 1.5, 56, -1.3])
            xyzrpy = [335, 0, 330, -180, 0, 0]
        # self._arm.set_mode(1)
        self._arm.set_position(
            x=xyzrpy[0],
            y=xyzrpy[1],
            z=xyzrpy[2],
            roll=xyzrpy[3],
            pitch=xyzrpy[4],
            yaw=xyzrpy[5],
        )
        self._arm.set_gripper_position(800)
        self._gripper_state_open = True
        # self._arm.set_servo_angle(angle=av, is_radian=True)
        # self._arm.set_mode(0)

        obs = self.get_obs(robot_in_safe_state=True, is_first=True)
        print("Reset done!")
        return obs

    def render(self) -> np.ndarray:
        """TODO"""
        raise NotImplementedError

    def close(self) -> None:
        """Nothing to close."""


def check_grasped_object(gripper_pos: float) -> bool:
    if gripper_pos > 0.015 and gripper_pos < 0.90:
        # gripper position can be slightly negative
        return True
    return False


class Side(enum.Enum):
    LEFT = 1
    RIGHT = 2
    OTHER = 3


class XArmPickPlace(BaseEnv):  # GraspRewardEnv

    POS_TOL = 40

    XYZ_MIN = (252, -170, 182)
    XYZ_MAX = (523, 178, 550)

    LEFT_XY_MIN = (252, 85)
    LEFT_XY_MAX = (523, 175)

    RIGHT_XY_MIN = (252, -170)
    RIGHT_XY_MAX = (523, -75)

    Z_TABLE = 182
    Z_HOVER = 290
    Z_RESET = 480
    COUNTDOWN_STEPS = 5

    def __init__(self, real: bool = True) -> None:
        self.grasped_object = False
        self.grasped_bin = Side.OTHER
        print("BALL MUST BE ON THE LEFT SIDE")
        print("BALL MUST BE ON THE LEFT SIDE")
        print("BALL MUST BE ON THE LEFT SIDE")
        print("BALL MUST BE ON THE LEFT SIDE")
        print("BALL MUST BE ON THE LEFT SIDE")
        self._ball_side = Side.LEFT
        self.countdown: Optional[int] = None
        super().__init__(EnvConfig(use_xarm=real))

    def _print_debug_info(self) -> None:
        print("Right Bound Min: {self.RIGHT_XY_MIN}")
        print("Right Bound Max: {self.RIGHT_XY_MAX}")
        print("Left  Bound Min: {self.LEFT_XY_MIN}")
        print("Left  Bound Max: {self.LEFT_XY_MAX}")
        traceback.print_stack()
        stacktrace = "".join(traceback.format_exception(*sys.exc_info()))
        print(stacktrace)

    def arm_side(
        self, margin: int = -2, allow_other: bool = False, only_y: bool = False
    ) -> Side:
        _, _, cart_pos = self.get_proprio()

        if only_y:
            x = cart_pos[0]
            if x < 255 or 520 < x:
                return Side.OTHER

            y = cart_pos[1]
            if y < self.RIGHT_XY_MAX[1] - margin:
                return Side.RIGHT
            elif self.LEFT_XY_MIN[1] + margin < y:
                return Side.LEFT
            elif allow_other:
                return Side.OTHER
            else:
                print("ARM NOT ON EITHER SIDE")
                print(cart_pos[:2])
                self._print_debug_info()
                self._reset()
                return self.arm_side(margin=margin, allow_other=allow_other)

        pos = np.array(cart_pos)[:2]
        if (np.array(self.RIGHT_XY_MIN) + margin <= pos).all() and (
            np.array(self.RIGHT_XY_MAX) - margin >= pos
        ).all():
            return Side.RIGHT
        elif (np.array(self.LEFT_XY_MIN) + margin <= pos).all() and (
            np.array(self.LEFT_XY_MAX) - margin >= pos
        ).all():
            return Side.LEFT
        elif allow_other:
            return Side.OTHER
        else:
            # self._arm.emergency_stop()
            print("ARM NOT ON EITHER SIDE")
            print(cart_pos[:2])
            self._print_debug_info()
            self._reset()
            return self.arm_side(margin=margin, allow_other=allow_other)

    def current_bounds(self) -> Tuple[np.ndarray, np.ndarray, float]:
        if self.grasped_object:
            return (
                np.array(self.XYZ_MIN[:2]),
                np.array(self.XYZ_MAX[:2]),
                self.Z_HOVER,
            )
        side = self.arm_side(margin=-52)  # margin=-self.cfg.max_delta_mm)
        if side == Side.LEFT:
            return (
                np.array(self.LEFT_XY_MIN),
                np.array(self.LEFT_XY_MAX),
                self.Z_TABLE,
            )
        elif side == Side.RIGHT:
            return (
                np.array(self.RIGHT_XY_MIN),
                np.array(self.RIGHT_XY_MAX),
                self.Z_TABLE,
            )
        else:
            raise NotImplementedError

    @property
    def act_space(self) -> Dict[str, embodied.Space]:
        return {
            "action": embodied.Space(np.int64, (), 0, 6),
        }

    def compute_arm_position(self, control_action: np.ndarray) -> np.ndarray:
        """Convert control action to TCP homogeneous transform.

        Args:
            env_config (EnvConfig): The environment configuration.
            control_action (np.ndarray, shape=self.control_shape()): control_action
            (should be values between -1 and 1, following the dm_control convention)
            curr_pose (np.ndarray, shape=(6, )): the current robot pose

        Returns:
            np.ndarray, shape=(6, ): The target pose.
        """
        control_action = np.clip(control_action, -1, 1) * self.cfg.max_delta_mm
        assert control_action.shape == (2,), control_action

        _, _, cart_pos = self.get_proprio()
        target_pose = np.array(cart_pos)
        target_pose[:2] = target_pose[:2] + control_action
        xy_min, xy_max, z_loc = self.current_bounds()
        if self.countdown is not None:
            z_loc = cart_pos[2]

        target_pose[:2] = (
            np.round(target_pose[:2] / self.cfg.max_delta_mm)
        ) * self.cfg.max_delta_mm
        target_pose[:2] = np.clip(target_pose[:2], xy_min, xy_max)
        target_pose[2] = z_loc
        if control_action[0] == 0:
            target_pose[0] = cart_pos[0]
        if control_action[1] == 0:
            target_pose[1] = cart_pos[1]
        return target_pose

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if action["reset"]:
            if action.get("manual_resume", False):
                return self.get_obs(robot_in_safe_state=True, is_first=True)
            else:

                return self._reset()

        if action["action"] < 4:
            pos_delta = ((-1, 0), (1, 0), (0, -1), (0, 1))[action["action"]]
            xyzrpy = self.compute_arm_position(np.array(pos_delta))
            self.set_position((xyzrpy[0], xyzrpy[1], xyzrpy[2]), wait=True)

        elif action["action"] == 4:  # close
            if self._gripper_state_open:
                self._arm.set_gripper_position(0, wait=True)
            self._gripper_state_open = False

        elif action["action"] == 5:  # open
            # no open if in center
            side = self.arm_side(margin=-22, only_y=True, allow_other=True)
            if self.grasped_object and (side == Side.OTHER):
                pass
            else:
                if not self._gripper_state_open:
                    self._arm.set_gripper_position(800, wait=True)
                self._gripper_state_open = True

        else:
            raise NotImplementedError(action)

        while self._arm.get_is_moving():
            time.sleep(0.01)

        self.rate.sleep()

        obs = self.get_obs(
            robot_in_safe_state=True, is_first=False
        )  # TODO: check safe state
        if obs["reward"] != 0:
            obs = self.get_obs(
                robot_in_safe_state=True, is_first=False, reward=obs["reward"]
            )

        if action.get("manual_pause", False):
            self._arm.set_gripper_position(800)

        if self.countdown is not None:
            print(self.countdown)
            self.countdown -= 1
            if self.countdown <= 0:
                obs["is_last"] = True

        return obs

    def _reset(self) -> Dict[str, Any]:
        if self.grasped_object:
            # move to random pos in bin
            if self.grasped_bin == Side.LEFT:
                xyz_min, xyz_max = self.LEFT_XY_MIN, self.LEFT_XY_MAX
            elif self.grasped_bin == Side.RIGHT:
                xyz_min, xyz_max = self.RIGHT_XY_MIN, self.RIGHT_XY_MAX
            else:
                raise NotImplementedError(f"ball side={self._ball_side}")
            x = np.random.uniform(xyz_min[0] + self.POS_TOL, xyz_max[0] - self.POS_TOL)
            y = np.random.uniform(xyz_min[1] + self.POS_TOL, xyz_max[1] - self.POS_TOL)
            self._arm.set_position(z=self.Z_RESET, speed=500, wait=True)

        # open gripper and reset gripper state
        self._arm.set_gripper_position(800, wait=True)
        self._gripper_state_open = True
        self.grasped_bin = Side.OTHER
        self.grasped_object = False

        # move to random pos
        if self._ball_side == Side.LEFT:
            xyz_min, xyz_max = self.LEFT_XY_MIN, self.LEFT_XY_MAX
        elif self._ball_side == Side.RIGHT:
            xyz_min, xyz_max = self.RIGHT_XY_MIN, self.RIGHT_XY_MAX
        else:
            raise NotImplementedError(f"ball side={self._ball_side}")
        x = np.random.uniform(xyz_min[0], xyz_max[0])
        y = np.random.uniform(xyz_min[1], xyz_max[1])
        self._arm.set_position(z=self.Z_RESET, speed=500, wait=True)
        self.set_position((x, y, self.Z_RESET), speed=500, wait=True)
        self.set_position((x, y, self.Z_TABLE), speed=50, wait=True)
        self.countdown = None
        obs = self.get_obs(robot_in_safe_state=True, is_first=True)
        return obs

        # self.grasped_object = False
        # self.grasped_bin = Side.OTHER
        # self._arm.set_gripper_position(800)
        # self._arm.set_position(z=self.Z_RESET, speed=200)  # lift arm
        #
        # if bool(random.randint(0, 1)):
        #     xyz_min, xyz_max = self.LEFT_XY_MIN, self.LEFT_XY_MAX
        # else:
        #     xyz_min, xyz_max = self.RIGHT_XY_MIN, self.RIGHT_XY_MAX
        # x = np.random.uniform(xyz_min[0] + self.POS_TOL, xyz_max[0] - self.POS_TOL)
        # y = np.random.uniform(xyz_min[1] + self.POS_TOL, xyz_max[1] - self.POS_TOL)
        #
        # self.set_position((x, y, self.Z_RESET), speed=50, wait=True)
        # time.sleep(2)
        #
        # self._gripper_state_open = True
        # x = np.random.uniform(xyz_min[0] + self.POS_TOL, xyz_max[0] - self.POS_TOL)
        # y = np.random.uniform(xyz_min[1] + self.POS_TOL, xyz_max[1] - self.POS_TOL)
        # self.set_position((x, y, self.Z_TABLE), wait=True, speed=100)
        #
        # time.sleep(2)
        # obs = self.get_obs(robot_in_safe_state=True, is_first=True)
        # print("Reset done!")
        # return obs

    def set_position(
        self, xyz: Tuple[float, float, float], wait: bool = False, speed: int = 800
    ) -> None:
        x, y, z = xyz
        self._arm.set_position(
            x=x, y=y, z=z, roll=-180, pitch=0, yaw=0, wait=wait, speed=speed
        )

    def get_reward(self, curr_obs: Dict[str, Any]) -> float:
        grasped_old = self.grasped_object
        grasped_new = check_grasped_object(curr_obs["gripper_pos"])
        self.grasped_object = grasped_new

        if not grasped_old and not grasped_new:  # not holding it
            return 0

        if not grasped_old and grasped_new:  # grasped it
            self.grasped_bin = self.arm_side(margin=-52)
            assert self.grasped_bin != Side.OTHER
            self._arm.set_position(z=self.Z_HOVER, wait=True)
            while self._arm.get_is_moving():
                time.sleep(0.001)
            return 1

        if grasped_old and not grasped_new:  # dropped it
            _as: Side = self.arm_side(margin=-52)
            if _as != self.grasped_bin:
                rew = 10
                self.countdown = self.COUNTDOWN_STEPS
                self._ball_side = _as
            else:
                rew = -1
                self._arm.set_position(z=self.Z_TABLE, wait=True)
                while self._arm.get_is_moving():
                    time.sleep(0.001)
            self.grasped_bin = Side.OTHER
            return rew

        if grasped_old and grasped_new:  # holding it
            return 0

        raise NotImplementedError


class XArm(BaseEnv):  # GraspRewardEnv
    def __init__(self, real: bool = True, random_reset: bool = True):
        self.random_reset = random_reset
        self.goal_index = 0
        self.pos_tol_mm = 50
        super().__init__(EnvConfig(use_xarm=real))

    @property
    def act_space(self) -> Dict[str, embodied.Space]:
        dims = super().act_space["robot_control"].shape[0] + 1
        return {
            "action": embodied.Space(np.float32, (dims,), -1, 1),
        }

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action = action.copy()
        action["robot_control"] = action["action"][:-1]
        action["gripper_control"] = action["action"][-1:]
        action.pop("action")
        obs = super().step(action)
        return obs

    def _reset(self) -> Dict[str, Any]:

        self._arm.set_gripper_position(0)
        x = np.random.uniform(XYZ_MIN[0], XYZ_MAX[0])
        y = np.random.uniform(XYZ_MIN[1], XYZ_MAX[1])
        xyzrpy = [x, y, 330, -180, 0, 0]
        self._arm.set_position(
            x=xyzrpy[0],
            y=xyzrpy[1],
            z=xyzrpy[2],
            roll=xyzrpy[3],
            pitch=xyzrpy[4],
            yaw=xyzrpy[5],
        )
        while self._arm.get_is_moving():
            time.sleep(0.001)
        self._arm.set_gripper_position(800)
        self._gripper_state_open = True
        if self.cfg.control_mode is ControlMode.DELTA_XY:
            if self.random_reset:
                x = np.random.uniform(XYZ_MIN[0], XYZ_MAX[0])
                y = np.random.uniform(XYZ_MIN[1], XYZ_MAX[1])
            else:
                x = 335
                y = 0
            xyzrpy = [x, y, 190, -180, 0, 0]
            self._arm.set_position(
                x=xyzrpy[0],
                y=xyzrpy[1],
                z=xyzrpy[2],
                roll=xyzrpy[3],
                pitch=xyzrpy[4],
                yaw=xyzrpy[5],
            )
        # self._arm.set_servo_angle(angle=av, is_radian=True)
        # self._arm.set_mode(0)

        while self._arm.get_is_moving():
            time.sleep(0.001)
        obs = self.get_obs(robot_in_safe_state=True, is_first=True)
        print("Reset done!")
        return obs

    def get_reward(self, curr_obs: Dict[str, Any]) -> float:
        if check_grasped_object(curr_obs["gripper_pos"]):
            return 1
        else:
            return 0


class UnsafeTestAgent:
    def __init__(self, env_config: EnvConfig) -> None:
        self._cfg = env_config

    def act(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        del obs  # not used

        assert self._cfg.control_mode in [ControlMode.DELTA_XY, ControlMode.DELTA_XYZ]
        control_action = np.array([1.0] * self._cfg.control_mode.control_shape()[0])

        # randomize direction of action
        control_action = (
            np.random.choice([-1, 1], control_action.shape) * control_action
        )
        return {
            "robot_control": control_action,
            "gripper_control": np.random.uniform(-1, 1),
        }


class SpaceMouseAgent:
    def __init__(self, env_config: EnvConfig) -> None:
        self._cfg = env_config
        self._mouse = SpaceMouse()
        self._gripper_open = True

    def act(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        del obs  # not used

        assert self._cfg.control_mode in [ControlMode.DELTA_XY, ControlMode.DELTA_XYZ]
        input_position = np.zeros(self._cfg.control_mode.control_shape())
        if np.linalg.norm(self._mouse.input_pos) > 10:
            # print(self._mouse.input_pos)
            input_position = (
                np.asarray(
                    [
                        self._mouse.input_pos[1],
                        self._mouse.input_pos[0],
                        -self._mouse.input_pos[2],
                    ]
                )
                / 350
            )
            input_position = input_position[: self._cfg.control_mode.control_shape()[0]]

        if input_position[0] > 0.2:
            return {"action": 0}
        elif input_position[0] < -0.2:
            return {"action": 1}
        elif input_position[1] > 0.2:
            return {"action": 2}
        elif input_position[1] < -0.2:
            return {"action": 3}

        if self._mouse.input_button1:
            if self._gripper_open:
                self._gripper_open = False
                return {"action": 4}
            else:
                self._gripper_open = True
                return {"action": 5}

        if self._gripper_open:
            return {"action": 5}
        else:
            return {"action": 4}


def main(env_config: EnvConfig) -> None:
    # select an env
    # env = KeyRewardEnv(env_config)
    # env = CornerRewardEnv(env_config)
    env = XArmPickPlace()

    # select an agent
    # agent = UnsafeTestAgent(env_config)
    agent = SpaceMouseAgent(env_config)
    print(f"==> Running the environment with {agent}")

    # obs = env._reset()
    while True:
        try:
            action = agent.act(None)
        except IndexError:
            break
        t = time.time()
        action["reset"] = False
        obs = env.step(action)
        reward = obs["reward"]
        if np.abs(reward) > 0.5:
            print(f"Step time : {time.time() - t}, reward: {reward}")
        if obs["is_last"]:
            env.step({"reset": True})

    obs = env._reset()
    print("==> Finishing to run the environment")


if __name__ == "__main__":
    main(dcargs.parse(EnvConfig))
