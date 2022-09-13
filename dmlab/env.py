# coding=utf-8
# Copyright 2019 The SEED Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DeepMind Lab Gym wrapper."""

import hashlib
import os

from absl import flags
from absl import logging
import time
import gym
import numpy as np
from seed_rl.common import common_flags
from seed_rl.dmlab import games
import tensorflow as tf
import torch
import torch.nn
from torchtext.vocab import GloVe
from torchtext.data.utils import get_tokenizer
import deepmind_lab

FLAGS = flags.FLAGS

flags.DEFINE_string('homepath', '', 'Labyrinth homepath.')
flags.DEFINE_string(
    'dataset_path', '/dataset', 'Path to dataset needed for psychlab_*, see '
    'https://github.com/deepmind/lab/tree/master/data/brady_konkle_oliva2008')

flags.DEFINE_string('game', 'explore_goal_locations_small', 'Game/level name.')
flags.DEFINE_integer('width', 96, 'Width of observation.')
flags.DEFINE_integer('height', 72, 'Height of observation.')
flags.DEFINE_string('level_cache_dir', None, 'Global level cache directory.')


DEFAULT_ACTION_SET = (
    (0, 0, 0, 1, 0, 0, 0),    # Forward
    (0, 0, 0, -1, 0, 0, 0),   # Backward
    (0, 0, -1, 0, 0, 0, 0),   # Strafe Left
    (0, 0, 1, 0, 0, 0, 0),    # Strafe Right
    (-20, 0, 0, 0, 0, 0, 0),  # Look Left
    (20, 0, 0, 0, 0, 0, 0),   # Look Right
    (-20, 0, 0, 1, 0, 0, 0),  # Look Left + Forward
    (20, 0, 0, 1, 0, 0, 0),   # Look Right + Forward
    (0, 0, 0, 0, 1, 0, 0),    # Fire.
)

NEW_ACTION_SET = (
    (0, 0, 0, 1, 0, 0, 0),    # Forward
    (0, 0, 0, -1, 0, 0, 0),   # Backward
    (0, 0, -1, 0, 0, 0, 0),   # Strafe Left
    (0, 0, 1, 0, 0, 0, 0),    # Strafe Right
    (-20, 0, 0, 0, 0, 0, 0),  # Look Left
    (20, 0, 0, 0, 0, 0, 0),   # Look Right
    (-20, 0, 0, 1, 0, 0, 0),  # Look Left + Forward
    (20, 0, 0, 1, 0, 0, 0),   # Look Right + Forward
    (-40, 0, 0, 0, 0, 0, 0),  # Look Left
    (40, 0, 0, 0, 0, 0, 0),   # Look Right
    (-40, 0, 0, 1, 0, 0, 0),  # Look Left + Forward
    (40, 0, 0, 1, 0, 0, 0),   # Look Right + Forward
    (0, -20, 0, 0, 0, 0, 0),  # Look DOWN
    (0, 20, 0, 0, 0, 0, 0),   # Look UP
    (0, -20, 0, 1, 0, 0, 0),  # Look DOWN + Forward
    (0, 20, 0, 1, 0, 0, 0),   # Look UP + Forward
    (0, -40, 0, 0, 0, 0, 0),  # Look DOWN
    (0, 40, 0, 0, 0, 0, 0),   # Look UP
    (0, -40, 0, 1, 0, 0, 0),  # Look DOWN + Forward
    (0, 40, 0, 1, 0, 0, 0),   # Look UP + Forward
    (0, 0, 0, 0, 1, 0, 0),    # Fire.
    (0, 0, 0, 0, 0, 1, 0),    # JUMP.
    (0, 0, 0, 0, 0, 0, 1),    # CROUCH.
)

class LevelCache(object):
    """Level cache."""

    def __init__(self, cache_dir):
        self._cache_dir = cache_dir

    def get_path(self, key):
        key = hashlib.md5(key.encode('utf-8')).hexdigest()
        dir_, filename = key[:3], key[3:]
        return os.path.join(self._cache_dir, dir_, filename)

    def fetch(self, key, pk3_path):
        path = self.get_path(key)
        try:
            tf.io.gfile.copy(path, pk3_path, overwrite=True)
            return True
        except tf.errors.OpError:
            return False

    def write(self, key, pk3_path):
        path = self.get_path(key)
        if not tf.io.gfile.exists(path):
            tf.io.gfile.makedirs(os.path.dirname(path))
            tf.io.gfile.copy(pk3_path, path)

class DmLab_extra(gym.Env):
    """DeepMind Lab wrapper."""

    def __init__(self, game, seed, is_test, config, num_action_repeats=4,
                 action_set=DEFAULT_ACTION_SET, level_cache_dir='./level_cache'):
      if is_test:
          config['allowHoldOutLevels'] = 'true'
          # Mixer seed for evalution, see
          # https://github.com/deepmind/lab/blob/master/docs/users/python_api.md
          config['mixerSeed'] = 0x600D5EED
      self.level = game
      config['datasetPath'] = FLAGS.dataset_path

      self._num_action_repeats = num_action_repeats
      self._random_state = np.random.RandomState(seed=seed)
      if FLAGS.homepath:
          deepmind_lab.set_runfiles_path(FLAGS.homepath)
      self._env = deepmind_lab.Lab(
          level=self.level,
          observations=['RGB_INTERLEAVED', 'INSTR'],
          level_cache=LevelCache(
              level_cache_dir) if level_cache_dir else None,
          config={k: str(v) for k, v in config.items()},
      )
      self._action_set = action_set
      self.action_space = gym.spaces.Discrete(len(self._action_set))
      self.observation_space = gym.spaces.Box(
          low=0,
          high=255,
          shape=(config['height'], config['width'], 3),
          dtype=np.uint8)
      self.embedding_space = gym.spaces.Box(
          low=-1000,
          high=1000,
          shape=(10, 25),
          dtype=np.float32)
        

    def _observation(self):
        # return self._env.observations()['RGB_INTERLEAVED']
        obs =  self._env.observations()
        return [obs[k] for k in obs.keys()]

    def reset(self):
        self._env.reset(seed=self._random_state.randint(0, 2 ** 31 - 1))
        return self._observation()

    def step(self, action):
        raw_action = np.array(self._action_set[action], np.intc)
        try:
            reward = self._env.step(raw_action, num_steps=self._num_action_repeats)
        except Exception as e:
            print(e.__class__.__name__, e)
            observation = None
            instruction = None
            reward = np.array(0.)
            done = np.array(True)
            return [observation, instruction], reward, done, {}
        done = not self._env.is_running()
        if done:
          observation = None
          instruction = None
        else:
          observation, instruction = self._observation()
        return [observation, instruction], reward, done, {}

    def close(self):
        self._env.close()


class DmLab(gym.Env):
    """DeepMind Lab wrapper."""

    def __init__(self, game, seed, is_test, config, num_action_repeats=4,
                 action_set=DEFAULT_ACTION_SET, level_cache_dir='./level_cache'):
      if is_test:
          config['allowHoldOutLevels'] = 'true'
          # Mixer seed for evalution, see
          # https://github.com/deepmind/lab/blob/master/docs/users/python_api.md
          config['mixerSeed'] = 0x600D5EED
      self.level = game
      config['datasetPath'] = FLAGS.dataset_path

      self._num_action_repeats = num_action_repeats
      self._random_state = np.random.RandomState(seed=seed)
      if FLAGS.homepath:
          deepmind_lab.set_runfiles_path(FLAGS.homepath)
      self._env = deepmind_lab.Lab(
          level=self.level,
          observations=['RGB_INTERLEAVED', 'INSTR'],
          level_cache=LevelCache(
              level_cache_dir) if level_cache_dir else None,
          config={k: str(v) for k, v in config.items()},
      )
      self._action_set = action_set
      self.action_space = gym.spaces.Discrete(len(self._action_set))
      self.observation_space = gym.spaces.Box(
          low=0,
          high=255,
          shape=(config['height'], config['width'], 3),
          dtype=np.uint8)
        
    def _observation(self):
        return self._env.observations()['RGB_INTERLEAVED']

    def reset(self):
        self._env.reset(seed=self._random_state.randint(0, 2 ** 31 - 1))
        return self._observation()

    def step(self, action):
        raw_action = np.array(self._action_set[action], np.intc)
        reward = self._env.step(raw_action, num_steps=self._num_action_repeats)
        done = not self._env.is_running()
        observation = None if done else self._observation()
        return observation, reward, done, {}

    def close(self):
        self._env.close()


def create_environment(task, config):
  cur_game = None
  if games.tasksets_path.get(config.sub_task, -1) != -1:
    cur_game = games.tasksets_path[config.sub_task] + config.task_names[task % len(config.task_names)]
  else:
    for taskset in games.tasksets.items():
      if config.sub_task in taskset[1]:
        cur_game = games.tasksets_path[taskset[0]] + config.sub_task
        break
  if config.extra_input:
    logging.info('creating DmLab_extra')
    env = DmLab_extra(
        cur_game,
        seed=task,
        is_test=False,
        config={
            'width': config.width,
            'height': config.height,
            'logLevel': 'WARN',
        })
  else:
    logging.info('creating DmLab')
    env = DmLab(
        cur_game,
        seed=task,
        is_test=False,
        config={
            'width': config.width,
            'height': config.height,
            'logLevel': 'WARN',
        })
  logging.info('Action repeats: %s', env._num_action_repeats)
  logging.info('Creating environment: %s', env.level)
  return env
