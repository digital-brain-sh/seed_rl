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

r"""SEED actor."""

import os
import timeit

from absl import flags
from absl import logging
import numpy as np
from seed_rl import grpc
from seed_rl.common import common_flags  
from seed_rl.common import profiling
from seed_rl.common import utils
import tensorflow as tf


FLAGS = flags.FLAGS

flags.DEFINE_integer('task', 0, 'Task id.')
flags.DEFINE_integer('num_actors_with_summaries', 4,
                     'Number of actors that will log debug/profiling TF '
                     'summaries.')
flags.DEFINE_bool('render', False,
                  'Whether the first actor should render the environment.')


def are_summaries_enabled():
  return FLAGS.task < FLAGS.num_actors_with_summaries


def actor_loop(create_env_fn, config=None, log_period=30):
  """Main actor loop.

  Args:
    create_env_fn: Callable (taking the task ID as argument) that must return a
      newly created environment.
    config: Configuration of the training.
    log_period: How often to log in seconds.
  """
  if not config:
    config = FLAGS
  env_batch_size = FLAGS.env_batch_size
  logging.info('Starting actor loop. Task: %r. Environment batch size: %r',
               FLAGS.task, env_batch_size)
  if are_summaries_enabled():
    summary_writer = tf.summary.create_file_writer(
        os.path.join(FLAGS.logdir, 'actor_{}'.format(FLAGS.task)),
        flush_millis=20000, max_queue=1000)
    timer_cls = profiling.ExportingTimer
  else:
    summary_writer = tf.summary.create_noop_writer()
    timer_cls = utils.nullcontext

  actor_step = 0
  with summary_writer.as_default():
    while True:
      try:
        # Client to communicate with the learner.
        client = grpc.Client(FLAGS.server_address)
        utils.update_config(config, client)
        if FLAGS.extra_input:
          from seed_rl.common import env_wrappers_extra
          batched_env = env_wrappers_extra.BatchedEnvironment(
              create_env_fn, env_batch_size, FLAGS.task * env_batch_size, config)
        else:
          from seed_rl.common import env_wrappers
          batched_env = env_wrappers.BatchedEnvironment(
              create_env_fn, env_batch_size, FLAGS.task * env_batch_size, config)

        env_id = batched_env.env_ids
        run_id = np.random.randint(
            low=0,
            high=np.iinfo(np.int64).max,
            size=env_batch_size,
            dtype=np.int64)
        if FLAGS.extra_input:
          observation, instruction, embedding, inst_len = batched_env.reset()
        else:
          observation = batched_env.reset()
        reward = np.zeros(env_batch_size, np.float32)
        raw_reward = np.zeros(env_batch_size, np.float32)
        done = np.zeros(env_batch_size, np.bool)
        abandoned = np.zeros(env_batch_size, np.bool)

        global_step = 0
        episode_step = np.zeros(env_batch_size, np.int32)
        episode_return = np.zeros(env_batch_size, np.float32)
        episode_raw_return = np.zeros(env_batch_size, np.float32)
        episode_step_sum = 0
        episode_return_sum = 0
        episode_raw_return_sum = 0
        episodes_in_report = 0

        elapsed_inference_s_timer = timer_cls('actor/elapsed_inference_s', 1000)
        last_log_time = timeit.default_timer()
        last_global_step = 0
        while True:
          tf.summary.experimental.set_step(actor_step)
          if FLAGS.extra_input:
            env_output = utils.EnvOutput_extra(reward, done, observation, embedding, inst_len,
                                        abandoned, episode_step)
          else:
            env_output = utils.EnvOutput(reward, done, observation,
                                        abandoned, episode_step)
          with elapsed_inference_s_timer:
            action = client.inference(env_id, run_id, env_output, raw_reward)
          with timer_cls('actor/elapsed_env_step_s', 1000):
            if FLAGS.extra_input:
              [observation, instruction, embedding, inst_len], reward, done, info = batched_env.step(action.numpy())
              # print(embedding)
              # print(instruction)
              # print(reward)
              # print(done)
              # print(action.numpy())
            else:
              observation, reward, done, info = batched_env.step(action.numpy())
          for i in range(env_batch_size):
            episode_step[i] += 1
            episode_return[i] += reward[i]
            raw_reward[i] = float((info[i] or {}).get('score_reward',
                                                      reward[i]))
            episode_raw_return[i] += raw_reward[i]
            if done[i]:
              # Periodically log statistics.
              current_time = timeit.default_timer()
              episode_step_sum += episode_step[i]
              episode_return_sum += episode_return[i]
              episode_raw_return_sum += episode_raw_return[i]
              global_step += episode_step[i]
              episodes_in_report += 1
              if current_time - last_log_time >= log_period:
                logging.info(
                    'Actor steps: %i, Return: %f Raw return: %f '
                    'Episode steps: %f, Speed: %f steps/s', global_step,
                    episode_return_sum / episodes_in_report,
                    episode_raw_return_sum / episodes_in_report,
                    episode_step_sum / episodes_in_report,
                    (global_step - last_global_step) /
                    (current_time - last_log_time))
                last_global_step = global_step
                episode_return_sum = 0
                episode_raw_return_sum = 0
                episode_step_sum = 0
                episodes_in_report = 0
                last_log_time = current_time

              episode_step[i] = 0
              episode_return[i] = 0
              episode_raw_return[i] = 0

          # Finally, we reset the episode which will report the transition
          # from the terminal state to the resetted state in the next loop
          # iteration (with zero rewards).
          with timer_cls('actor/elapsed_env_reset_s', 10):
            if FLAGS.extra_input:
              observation, instruction, embedding, inst_len = batched_env.reset_if_done(done)
            else:
              observation = batched_env.reset_if_done(done)
          actor_step += 1
      except (tf.errors.UnavailableError, tf.errors.CancelledError):
        logging.info('Inference call failed. This is normal at the end of '
                     'training.')
        batched_env.close()
