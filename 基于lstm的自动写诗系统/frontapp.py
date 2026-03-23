from model import myPoetryModel
from torch.distributions import Categorical
from data import prepareData
import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt

# 设置超参数
learning_rate = 5e-3       # 学习率
model_path = None          # 预训练模型路径
epochs = 10               # 训练轮数
verbose = True             # 打印训练过程
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

def train(dataloader, ix2word, word2ix):
    # 配置模型，是否继续上一次的训练
    model = myPoetryModel(len(word2ix))
    if model_path:
        model.load_state_dict(torch.load(model_path))
    model.to(device)

    # 设置优化器
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # 设置损失函数
    criterion = nn.CrossEntropyLoss()

    # 用于记录损失值
    losses = []

    # 定义训练过程
    for epoch in range(epochs):
        epoch_loss = 0
        for batch_idx, data in enumerate(dataloader):
            data = data.long().transpose(1, 0).contiguous()
            data = data.to(device)
            input, target = data[:-1, :], data[1:, :]
            output, _ = model(input)
            loss = criterion(output, target.view(-1))

            epoch_loss += loss.item()

            if batch_idx % 900 == 0 and verbose:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                    epoch + 1, batch_idx * len(data[1]), len(dataloader.dataset),
                    100. * batch_idx / len(dataloader), loss.item()))

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # 记录每个 epoch 的平均损失
        avg_loss = epoch_loss / len(dataloader)
        losses.append(avg_loss)
        print(f'Epoch {epoch + 1} finished. Average Loss: {avg_loss:.6f}')

    # 保存模型
    torch.save(model.state_dict(), 'myPoetryModel.pth')

    # 绘制损失函数图
    plt.figure(figsize=(10, 5))
    plt.plot(range(1, epochs + 1), losses, label='Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training Loss Over Epochs')
    plt.legend()
    plt.grid(True)
    plt.savefig('training_loss.png')
    plt.show()

# 准备数据
dataloader, ix2word, word2ix = prepareData()

# 开始训练
train(dataloader, ix2word, word2ix)