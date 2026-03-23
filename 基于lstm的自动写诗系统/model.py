import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from data import prepareData
import torch.nn.functional as F


class PoetryModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim):
        super(PoetryModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        #self.gru = nn.GRU(embedding_dim, self.hidden_dim, num_layers=2)
        self.lstm = nn.LSTM(embedding_dim, self.hidden_dim, num_layers=2)
        self.linear = nn.Linear(self.hidden_dim, vocab_size)

    def forward(self, input, hidden=None):
        seq_len, batch_size = input.size()

        if hidden is None:
            h_0 = input.data.new(2, batch_size, self.hidden_dim).fill_(0).float()
            c_0 = input.data.new(2, batch_size, self.hidden_dim).fill_(0).float()
        else:
            h_0, c_0 = hidden
        # if hidden is None:
        #     # For GRU
        #     hidden = input.data.new(2, batch_size, self.hidden_dim).fill_(0).float()

        embeds = self.embedding(input)
        #output, hidden = self.gru(embeds,hidden)
        output, hidden = self.lstm(embeds, (h_0, c_0))
        output = self.linear(output.view(seq_len * batch_size, -1))
        return output, hidden


import torch
import torch.nn as nn
import torch.nn.functional as F


class myPoetryModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim=64, hidden_dim=128, num_layers=2, dropout_prob=0):
        super(myPoetryModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # 词嵌入层
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # LSTM层（dropout 在多层 LSTM 中会在层与层之间生效）
        self.lstm = nn.LSTM(
            embedding_dim,
            hidden_dim,
            num_layers=num_layers,
            dropout=(dropout_prob if num_layers > 1 else 0),  # 单层时 dropout 无效
            batch_first=False
        )

        # Dropout层（可在全连接层前加入）
        self.dropout = nn.Dropout(dropout_prob)

        # 输出层
        self.linear = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        """
        x: (seq_len, batch_size)
        """
        # 词嵌入, 得到 (seq_len, batch_size, embedding_dim)
        emb = self.embedding(x)

        # 如果需要，可以在嵌入后加 dropout
        emb = self.dropout(emb)

        # 初始化隐藏状态，如果没有给定 hidden
        if hidden is None:
            h_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(x.device)
            c_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(x.device)
            hidden = (h_0, c_0)

        # LSTM 前向传播
        lstm_out, hidden = self.lstm(emb, hidden)  # lstm_out: (seq_len, batch_size, hidden_dim)

        # 可以对 lstm_out 进行 dropout
        lstm_out = self.dropout(lstm_out)

        # 全连接层，先将 lstm_out 变为 (seq_len * batch_size, hidden_dim)
        output = self.linear(lstm_out.contiguous().view(-1, self.hidden_dim))

        return output, hidden




class NormLSTMPoetryModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim=128, hidden_dim=256, num_layers=2):
        super(NormLSTMPoetryModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # 词嵌入层
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # LSTM层
        self.lstm = nn.LSTM(embedding_dim,
                            hidden_dim,
                            num_layers=num_layers,
                            batch_first=False)

        # 层标准化（关键改进）
        self.layernorm = nn.LayerNorm(hidden_dim)

        # 输出层
        self.linear = nn.Linear(hidden_dim, vocab_size)

        # 初始化forget gate偏置为1（提升训练稳定性）
        for name, param in self.lstm.named_parameters():
            if 'bias' in name:
                param.data[hidden_dim:2 * hidden_dim].fill_(1.0)

    def forward(self, x, hidden=None):
        # 输入形状: (seq_len, batch_size)
        emb = self.embedding(x)  # (seq_len, batch_size, embedding_dim)

        # 初始化隐藏状态
        if hidden is None:
            device = x.device
            h_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(device)
            c_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(device)
            hidden = (h_0, c_0)

        # LSTM前向传播
        lstm_out, hidden = self.lstm(emb, hidden)

        # 层标准化（关键位置）
        lstm_out = self.layernorm(lstm_out)

        # 全连接层
        output = self.linear(lstm_out.view(-1, self.hidden_dim))

        return output, hidden


import torch
import torch.nn as nn
import torch.nn.functional as F

import torch
import torch.nn as nn
import torch.nn.functional as F

class myPoetryModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim=128, hidden_dim=256, num_layers=2, penalty_weight=0.8):
        """
        :param vocab_size: 词表大小
        :param embedding_dim: 词嵌入维度
        :param hidden_dim: LSTM 隐藏状态维度
        :param num_layers: LSTM 层数
        :param penalty_weight: 对于连续重复 token 的惩罚权重，默认值 1.0
        """
        super(myPoetryModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.penalty_weight = penalty_weight

        # 词嵌入层
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # LSTM层
        self.lstm = nn.LSTM(embedding_dim,
                            hidden_dim,
                            num_layers=num_layers,
                            batch_first=False)

        # 层标准化（关键改进）
        self.layernorm = nn.LayerNorm(hidden_dim)

        # 输出层
        self.linear = nn.Linear(hidden_dim, vocab_size)

        # 初始化忘记门偏置为 1（提升训练稳定性）
        for name, param in self.lstm.named_parameters():
            if 'bias' in name:
                # LSTM 的 bias 按顺序排列为 [input, forget, cell, output]，
                # 将忘记门部分（hidden_dim 到 2*hidden_dim）的偏置初始化为 1
                param.data[hidden_dim:2 * hidden_dim].fill_(1.0)

    def forward(self, x, hidden=None):
        """
        :param x: 输入序列，形状 (seq_len, batch_size)
        :param hidden: 隐藏状态，默认为 None 时初始化
        :return: 输出 logits (形状为 (seq_len * batch_size, vocab_size)) 和更新后的 hidden 状态
        """
        # 词嵌入: (seq_len, batch_size, embedding_dim)
        emb = self.embedding(x)

        # 初始化隐藏状态（如果未提供）
        if hidden is None:
            device = x.device
            h_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(device)
            c_0 = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(device)
            hidden = (h_0, c_0)

        # LSTM 前向传播
        lstm_out, hidden = self.lstm(emb, hidden)  # lstm_out: (seq_len, batch_size, hidden_dim)

        # 层标准化
        lstm_out = self.layernorm(lstm_out)

        # 全连接输出: 得到 logits，形状 (seq_len, batch_size, vocab_size)
        logits = self.linear(lstm_out)

        # ----- 加入惩罚机制：对连续重复的 token 施加惩罚 -----
        # 这里我们假设输入 x 是教师强制下的正确序列，
        # 如果 x[t] 与 x[t-1] 相同，则在对应时间步 t 的 logits 内，
        # 将该 token 对应的 logit 值减去一个惩罚项，
        # 从而使得模型对重复输出的 token 得分下降。
        if x.size(0) > 1 and self.penalty_weight > 0:
            # 计算重复 mask：对于 t=1～(seq_len-1)，如果 x[t]==x[t-1]，则 mask=1，否则为0
            # shape: (seq_len-1, batch_size)
            repeat_mask = (x[1:] == x[:-1]).float()
            # 将后续的 token 转为 one-hot 表示，形状: (seq_len-1, batch_size, vocab_size)
            onehot = F.one_hot(x[1:], num_classes=logits.size(-1)).float()
            # 惩罚项 = penalty_weight * log(1 + count) 的简单版本，此处直接用常数惩罚
            # 这里我们直接减去 penalty_weight（可视为 log(1+1) * penalty_weight）；
            # 若需要更复杂的形式，可根据累计重复次数计算
            penalty = self.penalty_weight * repeat_mask.unsqueeze(-1) * onehot  # (seq_len-1, batch_size, vocab_size)
            # 对 logits 的 t>=1 时刻施加惩罚
            logits[1:] = logits[1:] - penalty

        # 将 logits reshape 为 (seq_len * batch_size, vocab_size)
        output = logits.view(-1, logits.size(-1))
        return output, hidden


class RNNPoetryModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim=128, hidden_dim=256, num_layers=2):
        super(RNNPoetryModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # 字符嵌入层
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

        # RNN层（使用Tanh激活）
        self.rnn = nn.RNN(embedding_dim,
                          hidden_dim,
                          num_layers=num_layers,
                          nonlinearity='tanh',
                          batch_first=True)

        # 层标准化
        self.layernorm = nn.LayerNorm(hidden_dim)

        # 输出层
        self.fc = nn.Linear(hidden_dim, vocab_size)

        # 初始化参数
        self.init_weights()

    def init_weights(self):
        init_range = 0.1
        self.embedding.weight.data.uniform_(-init_range, init_range)
        self.fc.bias.data.zero_()
        self.fc.weight.data.uniform_(-init_range, init_range)

    def forward(self, x, hidden=None):
        # 输入形状: (seq_len, batch_size)
        emb = self.embedding(x)  # (seq_len, batch_size, emb_dim)

        # 初始化隐藏状态
        if hidden is None:
            device = x.device
            hidden = torch.zeros(self.num_layers, x.size(1), self.hidden_dim).to(device)

        # RNN前向传播
        out, hidden = self.rnn(emb, hidden)

        # 层标准化
        out = self.layernorm(out)

        # 输出预测
        logits = self.fc(out.view(-1, self.hidden_dim))
        return logits, hidden