# train_eval.py

import time
import numpy as np
import tensorflow as tf
import os
import argparse

# Import modules
from config import Config, TestConfig
from ptb_data_producer import ptb_raw_data, create_ptb_dataset
from lstm_model import PTBModel


# Define a perplexity metric (optional, Keras doesn't have it built-in directly)
class Perplexity(tf.keras.metrics.Metric):
    def __init__(self, name='perplexity', **kwargs):
        super(Perplexity, self).__init__(name=name, **kwargs)
        self.total_loss = self.add_weight(name='total_loss', initializer='zeros')
        self.count = self.add_weight(name='count', initializer='zeros')

    def update_state(self, y_true, y_pred, sample_weight=None):
        # y_pred are logits, y_true are integer ids
        loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True,
                                                                reduction=tf.keras.losses.Reduction.SUM)
        # Flatten y_true and y_pred for loss calculation
        y_true_flat = tf.reshape(y_true, [-1])
        y_pred_flat = tf.reshape(y_pred, [-1, y_pred.shape[-1]])

        current_loss = loss_fn(y_true_flat, y_pred_flat)
        self.total_loss.assign_add(current_loss)
        self.count.assign_add(tf.cast(tf.size(y_true), self.dtype))  # Count number of predictions

    def result(self):
        # Perplexity is exp(average_cross_entropy)
        return tf.exp(self.total_loss / self.count)

    def reset_state(self):
        self.total_loss.assign(0.)
        self.count.assign(0.)


# Use tf.function for performance
@tf.function
def train_step(model, optimizer, loss_fn, inputs, targets):
    with tf.GradientTape() as tape:
        logits = model(inputs, training=True)
        # Reshape logits and targets for loss calculation
        logits_flat = tf.reshape(logits, [-1, logits.shape[-1]])  # (batch_size * num_steps, vocab_size)
        targets_flat = tf.reshape(targets, [-1])  # (batch_size * num_steps,)
        loss = loss_fn(targets_flat, logits_flat)
    gradients = tape.gradient(loss, model.trainable_variables)
    # Clip gradients
    gradients = [(tf.clip_by_norm(grad, model.config.max_grad_norm) if grad is not None else None)
                 for grad in gradients]
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    return loss


@tf.function
def eval_step(model, loss_fn, inputs, targets):
    logits = model(inputs, training=False)
    logits_flat = tf.reshape(logits, [-1, logits.shape[-1]])
    targets_flat = tf.reshape(targets, [-1])
    loss = loss_fn(targets_flat, logits_flat)
    return loss, logits  # Return logits for perplexity metric


def run_epoch(model, dataset, is_training, optimizer=None, verbose=False, epoch_info=""):
    total_loss_sum = 0.0
    total_words = 0

    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True, reduction=tf.keras.losses.Reduction.NONE)

    start_time = time.time()
    for batch_num, (inputs, targets) in enumerate(dataset):
        if is_training:
            batch_loss = train_step(model, optimizer, loss_fn, inputs, targets)
        else:
            batch_loss, logits = eval_step(model, loss_fn, inputs, targets)

        total_loss_sum += tf.reduce_sum(batch_loss).numpy()
        total_words += tf.size(targets).numpy()

        # Get the total number of steps in the dataset for proper verbose printing
        dataset_cardinality = tf.data.experimental.cardinality(dataset).numpy()
        if dataset_cardinality == tf.data.UNKNOWN_CARDINALITY:
            # Fallback for datasets with unknown cardinality (e.g., from_generator without output_signature)
            # This makes verbose printing less useful without a total step count
            total_steps_for_verbose = None  # Or an estimate if available
        else:
            total_steps_for_verbose = dataset_cardinality

        if verbose and (total_steps_for_verbose is not None) and \
                batch_num % max(1, total_steps_for_verbose // 10) == 0 and batch_num > 0:
            current_perplexity = np.exp(total_loss_sum / total_words)
            speed = total_words / (time.time() - start_time)
            print(f"{epoch_info} Step: {batch_num}/{total_steps_for_verbose} "
                  f"Perplexity: {current_perplexity:.3f} Speed: {speed:.0f} wps")

    final_perplexity = np.exp(total_loss_sum / total_words)
    return final_perplexity


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate a Neural Network Language Model.")
    parser.add_argument("--data_path", type=str, default='./data/simple-examples/data',
                        help="Where the training/test data is stored.")
    parser.add_argument("--save_path", type=str, default='./output',
                        help="Model output directory.")
    parser.add_argument("--num_gpus", type=int, default=0,  # num_gpus will be handled by tf.distribute if used.
                        help="Number of GPUs to use for training (currently for logging only).")
    parser.add_argument("--mode", type=str, default="train",
                        help="Mode: 'train' or 'test'")
    parser.add_argument("--train_percentage", type=float, default=1,
                        help="Percentage of training data to use (e.g., 0.1 for 10%).")
    args = parser.parse_args()

    if not args.data_path:
        raise ValueError("Must set --data_path to PTB data directory")

    # Load raw data
    raw_data = ptb_raw_data(args.data_path)
    train_data, valid_data, test_data, vocabulary = raw_data

    # Initialize configs
    config = Config()
    config.vocab_size = vocabulary
    eval_config = TestConfig()
    eval_config.vocab_size = vocabulary

    eval_config.batch_size = config.batch_size
    eval_config.num_steps = config.num_steps

    # Create tf.data.Dataset for train, valid, test
    train_dataset_full, train_epoch_size_full = create_ptb_dataset(train_data, config.batch_size, config.num_steps)
    valid_dataset, valid_epoch_size = create_ptb_dataset(valid_data, config.batch_size, config.num_steps)
    test_dataset, test_epoch_size = create_ptb_dataset(test_data, eval_config.batch_size, eval_config.num_steps)

    # --- Apply training data percentage here ---
    num_train_batches_to_use = int(train_epoch_size_full * args.train_percentage)
    if num_train_batches_to_use == 0 and train_epoch_size_full > 0:
        print(
            f"Warning: train_percentage {args.train_percentage} results in 0 batches. Using at least 1 batch if available.")
        num_train_batches_to_use = 1 if train_epoch_size_full > 0 else 0

    if num_train_batches_to_use > 0:
        train_dataset = train_dataset_full.take(num_train_batches_to_use)
        config.epoch_size = num_train_batches_to_use  # Update for logging
    else:
        # If no batches to train on, create an empty dataset
        print("No training batches to process. Check data or train_percentage.")
        train_dataset = tf.data.Dataset.from_tensors((tf.zeros([config.batch_size, config.num_steps], dtype=tf.int32),
                                                      tf.zeros([config.batch_size, config.num_steps],
                                                               dtype=tf.int32))).take(0)
        config.epoch_size = 0  # No batches for logging

    eval_config.epoch_size = test_epoch_size  # For consistency, although not directly used in run_epoch anymore

    # Initialize model
    model = PTBModel(config, vocabulary)

    # Optimizer and Loss
    optimizer = tf.keras.optimizers.SGD(learning_rate=config.learning_rate)

    # Loss function for training and evaluation
    train_loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True,
                                                                  reduction=tf.keras.losses.Reduction.NONE)

    # Build the model (needed for summary and to get input shapes right)
    dummy_input = tf.zeros((config.batch_size, config.num_steps), dtype=tf.int32)
    _ = model(dummy_input, training=False)
    model.summary()

    # Create checkpoint manager for saving/loading weights
    checkpoint = tf.train.Checkpoint(optimizer=optimizer, model=model)
    checkpoint_manager = tf.train.CheckpointManager(
        checkpoint, directory=args.save_path, max_to_keep=5
    )

    # Restore latest checkpoint if available
    if checkpoint_manager.latest_checkpoint:
        checkpoint.restore(checkpoint_manager.latest_checkpoint)
        print(f"Restored from {checkpoint_manager.latest_checkpoint}")

    print(f"Total trainable variables: {len(model.trainable_variables)}")

    if args.mode == "train":
        print("Starting training...")
        if config.epoch_size == 0:
            print("Skipping training as no batches are available.")
        else:
            for i in range(config.max_max_epoch):
                # Learning rate decay logic
                lr_decay_factor = config.lr_decay ** max(i + 1 - config.max_epoch, 0.0)
                new_lr_value = config.learning_rate * lr_decay_factor

                optimizer.learning_rate.assign(new_lr_value)

                print(f"Epoch: {i + 1} Learning rate: {optimizer.learning_rate.numpy():.3f}")

                # Training step
                train_perplexity = run_epoch(
                    model, train_dataset, is_training=True, optimizer=optimizer,
                    verbose=True, epoch_info=f"Epoch {i + 1} Train:"
                )
                print(f"Epoch: {i + 1} Train Perplexity: {train_perplexity:.3f}")

                # Validation step
                valid_perplexity = run_epoch(
                    model, valid_dataset, is_training=False, verbose=False,
                    epoch_info=f"Epoch {i + 1} Valid:"
                )
                print(f"Epoch: {i + 1} Valid Perplexity: {valid_perplexity:.3f}")

                # Save checkpoint
                if args.save_path:
                    save_path = checkpoint_manager.save()
                    print(f"Saved checkpoint for epoch {i + 1} at {save_path}")

            print("\nTraining finished.")
            # Final test evaluation after training
            print("Running final test evaluation...")
            test_perplexity = run_epoch(
                model, test_dataset, is_training=False, verbose=False,
                epoch_info="Final Test:"
            )
            print(f"Test Perplexity: {test_perplexity:.3f}")

    elif args.mode == "test":
        if not checkpoint_manager.latest_checkpoint:
            print("No checkpoint found to restore for testing. Please train a model first.")
            return

        print(f"Running test evaluation on restored model from {checkpoint_manager.latest_checkpoint}")
        test_perplexity = run_epoch(
            model, test_dataset, is_training=False, verbose=False,
            epoch_info="Test:"
        )
        print(f"Test Perplexity: {test_perplexity:.3f}")


if __name__ == "__main__":
    main()