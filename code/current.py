import argparse, math, random
import torch as th
import torch.nn as nn
import torchnet as tnt
import torchvision.transforms as T

from torch.autograd import Variable

from exptutils import *
import models, loader
from timeit import default_timer as timer

import numpy as np
import logging
from pprint import pprint
import pdb, glob, sys, gc, time, os
from copy import deepcopy

opt = add_args([
['-o', '/home/%s/local2/pratikac/results'%os.environ['USER'], 'output'],
['-m', 'lenett', 'lenett'],
['-g', 0, 'gpu'],
['--dataset', 'mnist', 'mnist'],
['--augment', False, 'augment'],
['-N', 1000, 'num images'],
['-b', 10, 'batch_size'],
['-B', 10000, 'max epochs'],
['--lr', 0.01, 'lr'],
['--l2', 0.0, 'l2'],
['--lrs', '', 'lr schedule'],
['-s', 42, 'seed'],
['-l', False, 'log'],
['-v', False, 'verbose']
])

setup(opt)

c = 16
opt['num_classes'] = 2
model = nn.Sequential(
    nn.Linear(49,c),
    nn.BatchNorm1d(c),
    nn.ReLU(True),
    nn.Linear(c,opt['num_classes'])
)
criterion = nn.CrossEntropyLoss()
optimizer = th.optim.SGD(model.parameters(), lr=opt['lr'],
            momentum=0.9, weight_decay=opt['l2'])

build_filename(opt, blacklist=['i'])
# pprint(opt)

def get_data():
    dataset, augment = getattr(loader, opt['dataset'])(opt)
    x, y = dataset['train']['x'], dataset['train']['y']

    xs, ys = [], []
    for i in xrange(opt['num_classes']):
        idx = (y==i).nonzero()[:opt['N']//opt['num_classes']].squeeze()

        tmp = []
        for ii in idx:
            t = T.ToPILImage()(x[ii].view(1,28,28))
            t = T.Scale(7)(t)
            t = T.ToTensor()(t)
            xs.append(t.view(1,49))
        ys.append(y[idx])
    x, y = th.cat(xs), th.cat(ys)
    idx = th.randperm(opt['N'])

    dataset = dict(train={'x': x, 'y': y}, val={'x': x, 'y': y})
    loaders = loader.get_loaders(dataset, augment, opt)
    train_data, val_data = loaders[0]['train_full'], loaders[0]['val']
    return train_data

train_data = get_data()

# dummy populate
for _, (x,y) in enumerate(train_data):
    _f = criterion(model(Variable(x)), Variable(y))
    _f.backward()
    break
w, dw = flatten_params(model)
print 'Num parameters: ', w.numel()

def train():
    dt = timer()

    opt['lr'] = lrschedule(opt, e)
    for p in optimizer.param_groups:
        p['lr'] = opt['lr']

    model.train()
    loss = tnt.meter.AverageValueMeter()
    top1 = tnt.meter.ClassErrorMeter()

    opt['nb'] = len(train_data)
    for b, (x,y) in enumerate(train_data):
        x,y = Variable(x), Variable(y)

        model.zero_grad()
        yh = model(x)
        f = criterion(yh, y)
        f.backward()

        optimizer.step()

        top1.add(yh.data, y.data)
        loss.add(f.data[0])

    r = dict(e=e, f=loss.value()[0], top1=top1.value()[0], train=True)
    print '+[%02d] %.3f %.3f%% %.2fs'%(e, r['f'], r['top1'], timer()-dt)
    return r

ws = []
for e in xrange(opt['B']):
    train()
    ws.append(w)

th.save(ws, 'current.pz')