# ptb_data_producer.py

import tensorflow as tf
import numpy as np
import collections
import os


def _read_words(filename):
    with tf.io.gfile.GFile(filename, "r") as f:
        return f.read().replace("\n", "<eos>").split()


def _build_vocab(filename):
    data = _read_words(filename)

    counter = collections.Counter(data)
    count_pairs = sorted(counter.items(), key=lambda x: (-x[1], x[0]))

    words, _ = list(zip(*count_pairs))
    word_to_id = dict(zip(words, range(len(words))))
    return word_to_id


def _file_to_word_ids(filename, word_to_id):
    data = _read_words(filename)
    return [word_to_id[word] for word in data if word in word_to_id]


def ptb_raw_data(data_path=None):
    """Load PTB raw data from data_path."""
    train_path = os.path.join(data_path, "ptb.train.txt")
    valid_path = os.path.join(data_path, "ptb.valid.txt")
    test_path = os.path.join(data_path, "ptb.test.txt")

    word_to_id = _build_vocab(train_path)
    train_data = _file_to_word_ids(train_path, word_to_id)
    valid_data = _file_to_word_ids(valid_path, word_to_id)
    test_data = _file_to_word_ids(test_path, word_to_id)
    vocabulary = len(word_to_id)
    return train_data, valid_data, test_data, vocabulary


def create_ptb_dataset(raw_data, batch_size, num_steps):
    """
    Creates a tf.data.Dataset for the PTB data.
    Each element of the dataset is a tuple (input_sequence, target_sequence).
    """
    raw_data = np.array(raw_data, dtype=np.int32)

    data_len = raw_data.shape[0]
    batch_len = data_len // batch_size
    data = raw_data[0: batch_size * batch_len].reshape(batch_size, batch_len)

    # Calculate number of full sequences per epoch
    # For a sequence length of N, we have N-1 steps in the target.
    # So, to get num_steps sequences, we need num_steps + 1 elements from batch_len.
    num_sequences_per_batch_row = (batch_len - 1) // num_steps

    # Create dataset from slices
    # The dataset will yield (batch_size, sequence_length) for input and target
    def generate_sequences():
        for i in range(num_sequences_per_batch_row):
            x = data[:, i * num_steps:(i + 1) * num_steps]
            y = data[:, i * num_steps + 1:(i + 1) * num_steps + 1]
            yield x, y

    # tf.data.Dataset.from_generator automatically handles parallelism and prefetching
    # if output_types and output_shapes are specified.
    dataset = tf.data.Dataset.from_generator(
        generate_sequences,
        output_types=(tf.int32, tf.int32),
        output_shapes=(tf.TensorShape([batch_size, num_steps]),
                       tf.TensorShape([batch_size, num_steps]))
    )

    # We can prefetch to improve performance
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    # Calculate epoch size for monitoring progress
    epoch_size = num_sequences_per_batch_row  # This is the number of batches per epoch
    if epoch_size == 0:
        raise ValueError(
            "epoch_size == 0, decrease batch_size or num_steps. "
            "Current: batch_size=%d, num_steps=%d, data_len=%d" %
            (batch_size, num_steps, data_len))

    return dataset, epoch_size