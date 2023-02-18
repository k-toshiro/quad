# Instructions
# ============
#
# 1. Test your setup:
#
# docker run -it --rm --gpus all tensorflow/tensorflow:2.8.0-gpu nvidia-smi
#
# 2. Train an agent:
#
# docker build -t image .
# docker run -it --rm --gpus all -v ~/logdir:/logdir image \
#   --logdir "/logdir/$(date +%Y%m%d-%H%M%S)" \
#   --configs atari --task atari_pong
#
# You may also need to add --privileged to the docker run commands.

FROM tensorflow/tensorflow:2.8.0-gpu

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC

# System packages.
RUN apt-get update && apt-get install -y \
  ffmpeg \
  libgl1-mesa-dev \
  python3-pip \
  unrar \
  vim \
  wget \
  git \
  && apt-get clean
# libx11-6 \
# openjdk-8-jdk \
# x11-xserver-utils \
# xvfb \

# MuJoCo.
ENV MUJOCO_GL egl
RUN mkdir -p /root/.mujoco && \
  wget -nv https://mujoco.org/download/mujoco210-linux-x86_64.tar.gz -O - | \
  tar -xz -C /root/.mujoco

# Python packages.
RUN pip3 install --disable-pip-version-check --no-cache-dir \
  gym==0.19.0 \
  attrs \
  cloudpickle \
  crafter>=1.7.1 \
  dm_control \
  dm_sonnet \
  filterpy \
  numpy \
  psutil \
  pybullet \
  ruamel.yaml \
  tensorflow_addons \
  tensorflow_hub \
  tensorflow_probability==0.16.0 \
  --use-feature=2020-resolver
# atari_py \
# minerl \

RUN apt update && \
  apt install -y \
  cmake \
  libboost-all-dev \
  libglib2.0-dev

# # Atari ROMS.
# RUN wget -L -nv http://www.atarimania.com/roms/Roms.rar && \
#   unrar x Roms.rar && \
#   unzip ROMS.zip && \
#   python3 -m atari_py.import_roms ROMS && \
#   rm -rf Roms.rar ROMS.zip ROMS

# Ensure prints are flushed.
ENV PYTHONUNBUFFERED 1

# Enable XLA.
# ENV TF_XLA_FLAGS --tf_xla_auto_jit=2
ENV TF_FUNCTION_JIT_COMPILE_DEFAULT 1

# This makes it work on multi GPU but breaks it on single GPU.
# ENV TF_FORCE_UNIFIED_MEMORY 1
ENV XLA_PYTHON_CLIENT_MEM_FRACTION 0.8

# Copy code.
COPY motion_imitation /motion_imitation
COPY embodied /embodied
# WORKDIR /embodied
RUN chown -R 1000:root /motion_imitation && chmod -R 775 /motion_imitation
RUN chown -R 1000:root /embodied && chmod -R 775 /embodied

# Unitree SDK
RUN mkdir /root/sdk && cd /root/sdk && \
  git clone https://github.com/lcm-proj/lcm && \
  git clone https://github.com/unitreerobotics/unitree_legged_sdk && \
  cd lcm && mkdir build && cd build && cmake ../ && make && make install && \
  cd ../../unitree_legged_sdk && git checkout v3.2 && mkdir build && cd build && cmake ../ && make

RUN mkdir /root/daydreamer
WORKDIR /root/daydreamer

# "sh", "xvfb_run.sh",
# CMD [ \
#   "python3", "embodied/agents/dreamerv3/train.py", \
#   "--logdir", "/logdir/run1", \
#   "--configs", "a1", "debug" \
# ]
