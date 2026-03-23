# config.py

import tensorflow as tf # Keep as tf

class Config(object):
    """Holds model hyperparameters."""

    def __init__(self):
        self.init_scale = 0.05
        self.learning_rate = 1.0 # Initial learning rate, will be decayed
        self.max_grad_norm = 5
        self.num_layers = 2
        self.num_steps = 35 # Sequence length for unrolling
        self.hidden_size = 650
        self.max_epoch = 6 # Epochs before starting learning rate decay
        self.max_max_epoch = 50 # Total number of epochs
        self.keep_prob = 0.5 # Dropout keep probability
        self.lr_decay = 0.8
        self.batch_size = 20
        self.vocab_size = 10000 # This will be updated based on actual data
        self.data_type = tf.float32

class TestConfig(Config):
    """Small config for testing/evaluation."""
    def __init__(self):
        super(TestConfig, self).__init__()
        self.init_scale = 0.1
        self.learning_rate = 1.0
        self.max_grad_norm = 1
        self.num_layers = 1
        self.num_steps = 2
        self.hidden_size = 2
        self.max_epoch = 1
        self.max_max_epoch = 1
        self.keep_prob = 1.0 # No dropout for evaluation
        self.lr_decay = 0.5
        self.batch_size = 20 # For testing, often 1 or a small number
        self.vocab_size = 10000