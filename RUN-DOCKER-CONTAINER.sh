#!/bin/bash


PROJECT_NAME=daydreamer3
PROJECT_CONTAINER_NAME=daydreamer_test3
CONTAINER_NAME=${PROJECT_CONTAINER_NAME}
IMAGE_NAME=${PROJECT_NAME}
TAG_NAME=latest

docker run -itd  \
    --gpus all \
    --net host \
    --env DISPLAY=${DISPLAY} \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v ~/logdir:/logdir \
    -v ${PWD}:/root/daydreamer \
    -e LD_LIBRARY_PATH=/root/sdk/unitree_legged_sdk/lib \
    --name ${CONTAINER_NAME} \
    ${IMAGE_NAME}:${TAG_NAME} \
    bash
