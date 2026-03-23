# lstm_model.py

import tensorflow as tf
from config import Config

class PTBModel(tf.keras.Model):
    """The PTB model, implemented as a tf.keras.Model."""

    def __init__(self, config, vocab_size):
        super(PTBModel, self).__init__()
        self.config = config
        self.vocab_size = vocab_size
        self.hidden_size = config.hidden_size
        self.num_layers = config.num_layers
        self.keep_prob = config.keep_prob
        self.data_type = config.data_type

        # Embedding layer
        self.embedding = tf.keras.layers.Embedding(
            input_dim=self.vocab_size,
            output_dim=self.hidden_size,
            embeddings_initializer=tf.random_uniform_initializer(
                -self.config.init_scale, self.config.init_scale),
            dtype=self.data_type
        )

        # Dropout layer for inputs
        self.dropout_input = tf.keras.layers.Dropout(1.0 - self.keep_prob)

        # Stacked LSTM layers
        self.lstm_layers = []
        for i in range(self.num_layers):
            lstm_layer = tf.keras.layers.LSTM(
                self.hidden_size,
                return_sequences=True, # All LSTM layers return sequences for stacking
                stateful=False, # We are not using stateful RNN for simplicity here
                kernel_initializer=tf.random_uniform_initializer(
                    -self.config.init_scale, self.config.init_scale),
                recurrent_initializer=tf.random_uniform_initializer(
                    -self.config.init_scale, self.config.init_scale),
                bias_initializer='zeros',
                dtype=self.data_type
            )
            self.lstm_layers.append(lstm_layer)
            # Add dropout between LSTM layers if keep_prob < 1 and not the last layer
            if i < self.num_layers - 1:
                self.lstm_layers.append(tf.keras.layers.Dropout(1.0 - self.keep_prob))


        # Output Dense layer (softmax layer in original code)
        self.output_dense = tf.keras.layers.Dense(
            units=self.vocab_size,
            kernel_initializer=tf.random_uniform_initializer(
                -self.config.init_scale, self.config.init_scale),
            bias_initializer='zeros',
            dtype=self.data_type
        )

    def call(self, inputs, training=False):
        # inputs shape: (batch_size, num_steps)

        # Embedding lookup
        embedded_inputs = self.embedding(inputs) # (batch_size, num_steps, hidden_size)

        # Apply dropout to inputs
        if training:
            embedded_inputs = self.dropout_input(embedded_inputs, training=training)

        # Pass through LSTM layers
        lstm_output = embedded_inputs
        for layer in self.lstm_layers:
            if isinstance(layer, tf.keras.layers.Dropout):
                lstm_output = layer(lstm_output, training=training)
            else: # Must be an LSTM layer
                lstm_output = layer(lstm_output) # (batch_size, num_steps, hidden_size)

        # Reshape output for Dense layer: (batch_size * num_steps, hidden_size)
        # Keras Dense layer applies to the last dimension, so (batch_size, num_steps, hidden_size) -> (batch_size, num_steps, vocab_size)
        logits = self.output_dense(lstm_output) # (batch_size, num_steps, vocab_size)

        return logits