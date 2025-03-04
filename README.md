# SEED
This repo is forked from [google-research/seed_rl](https://github.com/google-research/seed_rl). There are several changes for the training and data collection of dmlab and procgen tasks.
## Updates
- Add support for procgen and dmlab multi-task training.
- Add monitors for subtask episode return in multi-task training.
- Move logs to `~/logs/seed_rl/${game}_${agent}/${task}/${NUM_ACTORS}_${ENV_PER_ACTOR}_${PORT}_${CUDA}_${RUN_ID}` in host, path `~/logs/seed_rl` must be created in advance.

## Commands
### Building Docker images
Clone the repo first.
  ```bash
git clone https://github.com/digital-brain-sh/seed_rl.git
cd seed_rl
  ```
#### Images for DMLAB
We remove the file `DeepMind_Lab-1.0-py3-none-any.whl` in directory `./docker/prepare` due to its size. You can build it with the instructions in [deepmind/lab](https://github.com/deepmind/lab)

In the dockerfile, the `sources.list` and sources of pip are replaced for better internet connection. Be sure to adapt it according to your own connections.
  ```bash
docker build -t seed_rl:dmlab_0.0 -f docker/Dockerfile.dmlab1 .
docker build -t seed_rl:dmlab_0.1 -f docker/Dockerfile.dmlab2 .
docker build -t seed_rl:dmlab -f docker/Dockerfile.dmlab .
  ```

The image for dmlab could also be built with `docker build -t seed_rl:dmlab -f docker/Dockerfile.dmlab.old .`, perhaps.

#### Images for Procgen
  ```bash
docker build -t seed_rl:tf24py37 -f docker/Dockerfile.tf24py37 .
docker build -t seed_rl:procgen_0 -f docker/Dockerfile.procgen1 .
docker build -t seed_rl:procgen -f docker/Dockerfile.procgen .
  ```


### Training
The logs are at `~/logs/seed_rl/${game}_${agent}/${task}/${NUM_ACTORS}_${ENV_PER_ACTOR}_${PORT}_${CUDA}_${RUN_ID}`.

Trainings of several dmlab tasks with extra instructions are not supported yet. For example, the 'language' series of tasks.
```shell
./run_local.sh [Game] [Agent] [actors] [envs per actor] [task] [port for tensorboard] [cuda device] [run id]
# single task training
./run_local.sh procgen r2d2 100 4 bigfish 7000 7 0
./run_local.sh procgen r2d2 100 4 bossfight 7001 6 0
./run_local.sh procgen vtrace 100 4 bigfish 7001 6 0
./run_local.sh dmlab vtrace 100 4 rooms_watermaze 7001 6 0
./run_local.sh dmlab vtrace 100 4 lasertag_three_opponents_small 7000 6 0
./run_local.sh dmlab vtrace 100 4 seekavoid_arena_01 7000 6 0

# multi task training, details can be found in `./dmlab/games.py`
./run_local.sh dmlab vtrace 100 4 rooms 7001 6 0
./run_local.sh dmlab vtrace 100 4 lasers 7000 6 0
./run_local.sh dmlab vtrace 100 4 explore 7000 6 0
./run_local.sh dmlab vtrace 100 4 natlab 7000 5 0
```

### Data Collection
Before data collection, prepare the experts ckpt files in the following paths:

Procgen:
`./procgen_experts/${task}/ckpt-${CKPT_ID}.data-00000-of-00001`

DMlab:
`./dmlab_experts/${task}/ckpt-${CKPT_ID}.data-00000-of-00001`
```shell
./sample_local.sh [Game] [Agent] [actors] [envs per actor] [task] [cuda device] [CKPT_ID]
./sample_local.sh procgen r2d2 100 4 bigfish 7000 7 0
./sample_local.sh procgen r2d2 100 4 bossfight 7001 6 0
./sample_local.sh procgen vtrace 100 4 bigfish 7001 6 0
./sample_local.sh dmlab vtrace 10 4 explore_object_locations_small 6 240
./sample_local.sh dmlab vtrace 10 4 explore_object_locations_large 6 240
./sample_local.sh dmlab vtrace 10 8 explore_obstructed_goals_small 5 240
```


# SEED

This repository contains an implementation of distributed reinforcement learning
agent where both training and inference are performed on the learner.

<img src="./docs/architecture.gif" alt="Architecture" width="50%" height="50%">

Four agents are implemented:

- [IMPALA: Scalable Distributed Deep-RL with Importance Weighted Actor-Learner Architectures](https://arxiv.org/abs/1802.01561)

- [R2D2 (Recurrent Experience Replay in Distributed Reinforcement Learning)](https://openreview.net/forum?id=r1lyTjAqYX)

- [SAC: Soft Actor-Critic](https://arxiv.org/abs/1801.01290)

- [Configurable On-Policy Agent](https://arxiv.org/abs/2006.05990) implementing the following algorithms:
  - [Vanilla Policy Gradient](https://spinningup.openai.com/en/latest/algorithms/vpg.html)
  - [PPO: Proximal Policy Optimization](https://arxiv.org/abs/1707.06347)
  - [V-trace](https://arxiv.org/abs/1802.01561)
  - [AWR: Advantage-Weighted Regression](https://arxiv.org/abs/1910.00177)
  - [V-MPO: On-Policy Maximum a Posteriori Policy Optimization](https://arxiv.org/abs/1909.12238)

The code is already interfaced with the following environments:

- [ATARI games](https://github.com/openai/atari-py/tree/master/atari_py)

- [DeepMind lab](https://github.com/deepmind/lab)

- [Google Research Football](https://github.com/google-research/football)

- [Mujoco](https://github.com/openai/gym/tree/master/gym/envs/mujoco)

However, any reinforcement learning environment using the [gym
API](https://github.com/openai/gym/blob/master/gym/core.py) can be used.

For a detailed description of the architecture please read
[our paper](https://arxiv.org/abs/1910.06591).
Please cite the paper if you use the code from this repository in your work.

### Bibtex

```
@article{espeholt2019seed,
    title={SEED RL: Scalable and Efficient Deep-RL with Accelerated Central Inference},
    author={Lasse Espeholt and Rapha{\"e}l Marinier and Piotr Stanczyk and Ke Wang and Marcin Michalski},
    year={2019},
    eprint={1910.06591},
    archivePrefix={arXiv},
    primaryClass={cs.LG}
}
```

## Pull Requests

At this time, we do not accept pull requests. We are happy to link to forks
that add interesting functionality.

## Prerequisites

There are a few steps you need to take before playing with SEED. Instructions
below assume you run the Ubuntu distribution.

- Install docker by following instructions at https://docs.docker.com/install/linux/docker-ce/ubuntu/.
  You need 19.03 version or later due to required GPU support.

- Make sure docker works as non-root user by following instructions at
  https://docs.docker.com/install/linux/linux-postinstall, section
  **Manage Docker as a non-root user**.

- Install git:

```shell
apt-get install git
```

- Clone SEED git repository:

```shell
git clone https://github.com/google-research/seed_rl.git
cd seed_rl
```

## Local Machine Training on a Single Level

To easily start with SEED we provide a way of running it on a local
machine. You just need to run one of the following commands (adjusting
`number of actors` and `number of envs. per actor/env. batch size`
to your machine):

```shell
./run_local.sh [Game] [Agent] [number of actors] [number of envs. per actor]
./run_local.sh atari r2d2 4 4
./run_local.sh football vtrace 4 1
./run_local.sh dmlab vtrace 4 4
./run_local.sh mujoco ppo 4 32 --gin_config=/seed_rl/mujoco/gin/ppo.gin
```

It will build a Docker image using SEED source code and start the training
inside the Docker image. Note that hyper parameters are not tuned in the runs
above. Tensorboard is started as part of the training. It can be viewed under
[http://localhost:6006](http://localhost:6006) by default.

We also provide a sample script for running training with tuned parameters for
HalfCheetah-v2. This setup runs training with 8x32=256 parallel environments to
make training faster. The sample complexity can be improved at the cost
of slower training by running fewer environments and increasing the
`unroll_length` parameter.

```shell
./mujoco/local_baseline_HalfCheetah-v2.sh
```

## Distributed Training using AI Platform

Note that training with AI Platform results in charges for using compute resources.

The first step is to configure GCP and a Cloud project you will use for training:

- Install Cloud SDK following instructions at https://cloud.google.com/sdk/install
  and setup up your GCP project.
- Make sure that billing is enabled for your project.
- Enable the AI Platform ("Cloud Machine Learning Engine") and Compute Engine APIs.
- Grant access to the AI Platform service accounts as described at
  https://cloud.google.com/ml-engine/docs/working-with-cloud-storage.
- Cloud-authenticate in your shell, so that SEED scripts can use your project:

```shell
gcloud auth login
gcloud config set project [YOUR_PROJECT]
```

Then you just need to execute one of the provided scenarios:

```shell
gcp/train_[scenario_name].sh
```

This will build the Docker image, push it to the repository which AI Platform
can access and start the training process on the Cloud. Follow output of the command
for progress. You can also view the running training jobs at
https://console.cloud.google.com/ml/jobs

## DeepMind Lab Level Cache

By default majority of DeepMind Lab's CPU usage is generated by creating new
scenarios. This cost can be eliminated by enabling level cache. To enable it,
set the ```level_cache_dir``` flag in the ```dmlab/config.py```.
As there are many unique episodes it is a good idea to share the same cache
across multiple experiments.
For AI Platform you can add
```--level_cache_dir=gs://${BUCKET_NAME}/dmlab_cache```
to the list of parameters passed in ```gcp/submit.sh``` to the experiment.


## Baseline data on ATARI-57

We provide baseline training data for SEED's R2D2 trained on ATARI games in the
form of training curves (checkpoints and Tensorboard event files coming soon).
We provide data for 4 independent seeds run up to 40e9 environment frames.

The hyperparameters and evaluation procedure are the same as in section A.3.1 in
the [paper](https://arxiv.org/pdf/1910.06591.pdf).


### Training curves

Training curves are available on [this
page](https://github.com/google-research/seed_rl/tree/master/docs/r2d2_atari_training_curves.md).

### Checkpoints and Tensorboard event files

Checkpoints and tensorboard event files can be downloaded individually
[here](https://console.cloud.google.com/storage/browser/seed_rl_external_data_release)
or as [a single (70GBs) zip
file](https://storage.cloud.google.com/seed_rl_external_data_release/seed_r2d2_atari_checkpoints.zip).


## Additional links

SEED was used as a core infrastructure piece for the [What Matters In On-Policy Reinforcement Learning? A Large-Scale Empirical Study](https://arxiv.org/abs/2006.05990) paper.
A colab that reproduces plots from the paper can be found [here](https://github.com/google-research/seed_rl/tree/master/mujoco/what_matters_in_on_policy_rl.ipynb).
