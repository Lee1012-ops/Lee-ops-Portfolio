from model import myPoetryModel
from model import RNNPoetryModel
from torch.distributions import Categorical
from data import prepareData
import torch
import torch.nn as nn
# 设置超参数
learning_rate = 5e-3       # 学习率
model_path = None          # 预训练模型路径
epochs = 4             # 训练轮数
verbose = True             # 打印训练过程
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
def train(dataloader, ix2word, word2ix):
    # 配置模型，是否继续上一次的训练
    model =myPoetryModel(len(word2ix))
    if model_path:
        model.load_state_dict(torch.load(model_path))
    model.to(device)

    # 设置优化器
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # 设置损失函数
    criterion = nn.CrossEntropyLoss()

    # def entropy_loss(logits):
    #     probs = F.softmax(logits, dim=-1)
    #     dist = Categorical(probs)
    #     return -dist.entropy().mean()

    # 定义训练过程
    for epoch in range(epochs):
        for batch_idx, data in enumerate(dataloader):
            data = data.long().transpose(1, 0).contiguous()
            data = data.to(device)
            input, target = data[:-1, :], data[1:, :]
            output, _ = model(input)
            loss = criterion(output, target.view(-1))

            if batch_idx % 900 == 0 & verbose:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                    epoch + 1, batch_idx * len(data[1]), len(dataloader.dataset),
                    100. * batch_idx / len(dataloader), loss.item()))

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    # 保存模型
    torch.save(model.state_dict(), 'myPoetryModel.pth')
dataloader, ix2word, word2ix = prepareData()

train(dataloader, ix2word, word2ix)