from torch.utils.data import DataLoader
import numpy as np
import torch
import torch.nn as nn
def prepareData():
    # 读入预处理的数据
    datas = np.load("./dataset/tang.npz",allow_pickle=True)
    data = datas['data']
    ix2word = datas['ix2word'].item()
    word2ix = datas['word2ix'].item()

    # 转为torch.Tensor
    data = torch.from_numpy(data)
    dataloader = DataLoader(data,
                            batch_size=16,
                            shuffle=True,
                            num_workers=2)

    return dataloader, ix2word, word2ix