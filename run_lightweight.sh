# python embodied/agents/dreamerv3/train.py --configs a1 --logdir ~/logdir/$(date +%Y%m%d-%H%M%S) --batch_size 8 --replay_fixed.length 8 --train.log_every 1 --filter '_avg' --train.train_every 1 --train.train_fill 1 --'.*\.layers' 2 --'.*\.units' 256 --imag_horizon 7 --env.repeat 50 --task a1_real --actor.maxstd 0.2 --actor.minstd 0.01
python embodied/agents/dreamerv3/train.py --configs a1 --run train --logdir ~/logdir/$(date +%Y%m%d-%H%M%S) --batch_size 8 --replay_fixed.length 40 --train.log_every 1 --filter '_avg' --train.train_every 1 --train.train_fill 1 --'.*\.layers' 2 --'.*\.units' 256 --imag_horizon 7 --env.repeat 50 --task a1_real --actor.maxstd 0.2 --actor.minstd 0.01

# python embodied/agents/dreamerv3/train.py 
# --configs a1 
# --run train 
# --logdir ~/logdir/$(date +%Y%m%d-%H%M%S) 
# --batch_size 8 
# --replay_fixed.length 40 
# --train.log_every 1 
# --filter '_avg' 
# --train.train_every 1
# --train.train_fill 1
# --'.*\.layers' 2 
# --'.*\.units' 256 
# --imag_horizon 7 
# --env.repeat 50 
# --task a1_real 
# --actor.maxstd 0.2 
# --actor.minstd 0.01
