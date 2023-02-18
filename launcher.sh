#!/bin/sh
set -e
/google/bin/releases/xmanager/cli/xmanager.par launch launcher.py -- \
    --xm_deployment_env=alphabet \
    --xm_resource_alloc=user:xcloud/$USER \
    --noxm_monitor_on_launch
