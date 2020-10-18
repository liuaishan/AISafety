#!/usr/bin/env python
# coding=UTF-8
'''
@Author: Linna
@LastEditors: Linna
@Description: parent class to eval
@Date: 2019-05-22 14:26:09
@LastEditTime: 2020-09-22 17:02:55
'''

import argparse
import os
import random
import sys
import numpy as np
import torch
import torch.utils.data as Data
import cv2
import functools
from utils.EvalDataLoader import EvalDataset
from utils.file_utils import xmlparser
import torchvision
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, transforms
import PIL.Image as Image
import  matplotlib.pyplot as plt
sys.path.append('{}/'.format(os.path.dirname(os.path.realpath(__file__))))
sys.path.append('{}/../'.format(os.path.dirname(os.path.realpath(__file__))))
from EvalBox.Attack.AdvAttack import *
from EvalBox.Attack.CorAttack.corrupt import CORRUPT
import importlib
from torchvision.models import *
from utils.file_utils import get_user_model
from utils.io_utils import mkdir,configurate_Device
import cv2
import os.path
def file_extension(path):
  return os.path.splitext(path)[1]
#用户上传的图片类型
extension_lists=['.png','.tiff','.jpg']
#配置文件的参
config_file_type_list=['.xml','.ini']
#模型文件的类型
model_extension_pt_lists=['.pth','.pt']
model_extension_tf_lists=['.ckpt']

from abc import ABCMeta, abstractmethod
class Evaluation_Base(object):
    __metaclass__ = ABCMeta

    def __init__(self, attack_method,sample_path,label_path,image_origin_path,label_origin_path,
                 gpu_counts,gpu_indexs,seed,Scale_ImageSize,Crop_ImageSize,\
                                            model,model_dir, defense_model,model_defence_dir,data_type,IS_WHITE,\
                              IS_SAVE,IS_COMPARE_MODEL,IS_TARGETTED,save_path,save_method,black_Result_dir,batch_size):
        '''
        @description:
        @param {
            model:
        }
        @return:
        '''
        self.attack_method=attack_method
        self.gpu_counts=gpu_counts
        self.gpu_indexs=gpu_indexs
        self.seed=seed
        self.sample_path = sample_path
        self.label_path = label_path
        self.image_origin_path = image_origin_path
        self.label_origin_path = label_origin_path
        self.scale_image_size=Scale_ImageSize
        self.crop_image_size=Crop_ImageSize
    
    def get_predict(self,model,xs,device):
        var_xs = Variable(xs.to(device)).float()
        with torch.no_grad():
            outputs = model(var_xs)
            preds = torch.argmax(outputs, 1)
            preds = preds.data.cpu().numpy()
            origin_outputs = outputs.data.cpu().numpy()
        return origin_outputs, preds
    
    def adv_generate_batch_ys(self,device,ys,xs_data):
        var_ys = Variable(ys.to(device))
        for i in range(var_ys.cpu().numpy().shape[0]):
            adv_xadd = var_ys.cpu().numpy()[i]
            xs_data.append(adv_xadd)
        return xs_data
    
    def preds_eval(self,model,device,adv_xs):
        _, preds=self.get_predict(model,adv_xs,device)
        return preds
    
    def outputs_eval(self,model,device,adv_xs):
        outputs, _=self.get_predict(model,adv_xs,device)
        return outputs
    
    def get_origin_sample(self,device,dataloader):
        origin_xs_numpy = []
        for cln_xs, cln_ys in dataloader:
            origin_xs_numpy = self.adv_generate_batch_xs(device,cln_xs,origin_xs_numpy)
        return origin_xs_numpy
    
    def get_origin_ys(self,device,dataloader,dataloader_origin):
        cln_ys_numpy = []
        targeted_ys_numpy=[]
        for cln_xs, cln_ys in dataloader_origin:
            cln_ys_numpy = self.adv_generate_batch_ys(device,cln_ys,cln_ys_numpy)
        for xs, ys in dataloader:
            targeted_ys_numpy = self.adv_generate_batch_ys(device,ys,targeted_ys_numpy)
        return cln_ys_numpy, targeted_ys_numpy
    
    def white_eval(self,att,model,device,dataloader):
            adv_data = []
            class_num_type = 0
            for xs, ys in dataloader:
                if class_num_type == 0:
                    with torch.no_grad():
                        outputs = model(xs)
                        class_num_type = outputs.shape[1]
                adv_xs = att.generate(xs, ys)
                adv_data = self.adv_generate_batch_advs(model, device, adv_xs, adv_data)
            return class_num_type, adv_data
    
    def black_eval(self,model,device,dataloader):
            adv_data = []
            class_num_type = 0
            for adv_xs, ys  in dataloader:
                if class_num_type==0:
                    with torch.no_grad():
                        outputs = model(adv_xs)
                        class_num_type = outputs.shape[1]
                adv_data= self.adv_generate_batch_advs(model, device,  adv_xs, adv_data)
            return class_num_type, adv_data
    
    def get_model(self,model_dir,model_name,device):
        #使用预训练的网络，这个网络是ＩｍａｇｅＮｅｔ数据集上面的
        #看看模型是不是默认pytorch的格式
        if model_dir == '':
            Model_instance = eval(model_name)(pretrained=True)
            model =Model_instance.to(device)
        else :
            Model_instance = get_user_model(model_name)
            model = Model_instance.to(device)
            model.load_state_dict(torch.load(model_dir,map_location=device))
        return model
    
    def adv_generate_batch_xs(self, device, xs, xs_data):
        var_xs = Variable(xs.to(device))
        for i in range(var_xs.cpu().numpy().shape[0]):
            adv_xadd = var_xs.cpu().numpy()[i][np.newaxis, :]
            xs_data.extend(adv_xadd)
        return xs_data
    
    def adv_generate_batch_advs(self,model,device,xs,adv_data):
        var_xs = Variable(xs.to(device))
        for i in range(var_xs.cpu().numpy().shape[0]):
            adv_xadd = var_xs.cpu().numpy()[i][np.newaxis, :]
            adv_data.extend(adv_xadd)
        return adv_data

    def setting_device(self,model_dir,model_name):
        device=configurate_Device(self.seed,self.gpu_counts,self.gpu_indexs)
        self.device=device
        model = self.get_model(model_dir, model_name, device)
        att=None
        att_name=None
        if len(self.attack_method) == 1:
            A_instance = eval(self.attack_method[0])  #############
            att, att_name = A_instance(model, device, self.IS_TARGETTED), self.attack_method[0]  ############
        elif len(self.attack_method) == 2:
            cor_name = self.attack_method[1]

            att, att_name = CORRUPT(corruption_name=cor_name), self.attack_method[0]
        
        # 参数不使用默认参数,而是用户自定义的,第一个是方法名称，第二个是次级名称，第三个是参数的xml文件
        elif len(self.attack_method) == 3:
            if file_extension(self.attack_method[2]) in config_file_type_list:
                A_instance = eval(self.attack_method[0])  #############
                config_file_path = self.attack_method[2]
                args = xmlparser(config_file_path)
                if self.attack_method[0] == "CORRUPT":
                    att, att_name = CORRUPT(**args), self.attack_method[0]
                else:
                    att, att_name = A_instance(model, device, self.IS_TARGETTED, **args), self.attack_method[0]  ############
        return device,model,att,att_name
    
    def setting_dataset(self,image_size,sample_path,label_path):
        # .npy 的格式
        if file_extension(sample_path) == '.npy' and file_extension(self.label_path) == '.npy':
            # 批量化的图像攻击样本
            nature_samples = np.load(sample_path)
            labels_samples = np.load(label_path)
            xs = torch.from_numpy(nature_samples).float()
            ys = torch.argmax(torch.from_numpy(labels_samples), 1)
            #npy 一次性讀入
            #self.batch_size=xs.shape[0]
            dataset = Data.TensorDataset(xs, ys)
        # 常见图像格式的
        elif self.data_type == "ImageCustom":
            mytransform = transforms.Compose([
                transforms.Scale(image_size),
                transforms.CenterCrop((min(self.crop_image_size[0], image_size[0]), min(self.crop_image_size[1], image_size[1]))),
                transforms.ToTensor()
            ])
            dataset = EvalDataset(root_path=sample_path, label_path=label_path, origin_path=None, origin_label_path=None,
                                  data_type="ImageNet",
                                  image_size=image_size, transform=mytransform,
                                  ratio=1.0)
        else:
            #print("ImageNet type Folder")
            # 默认归一化的
            normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                             std=[0.229, 0.224, 0.225])
            mytransform = transforms.Compose([
                transforms.Scale(image_size),
                transforms.CenterCrop((min(self.crop_image_size[0], image_size[0]), min(self.crop_image_size[1], image_size[1]))),
                transforms.ToTensor(),
                normalize
            ])
            if (len(self.data_type) == 2 and self.data_type[0] == "ImageNet") and self.data_type[
                1] == "withoutNormalize":
                mytransform = transforms.Compose([
                    transforms.Scale(image_size),
                    transforms.CenterCrop((min(self.crop_image_size[0], image_size[0]), min(self.crop_image_size[1], image_size[1]))),
                    transforms.ToTensor(),
                ])
            # mytransform = transforms.Compose([transforms.ToTensor()])  # transform [0,255] to [0,1]
            dataset = EvalDataset(root_path=sample_path, label_path=label_path, origin_path=None, origin_label_path=None,
                                  data_type="ImageNet",
                                  image_size=image_size, transform=mytransform,
                                  ratio=1.0)
        #self.batch_size=dataset.__len__()
        dataloader = Data.DataLoader(dataset,batch_size=self.batch_size, num_workers=0, shuffle=False)
        return  dataloader,dataset

    def setting_model(self, model_dir, model_name,device):
        model = self.get_model(model_dir, model_name, device)
        model.eval().to(device)
        return model

    def estimate_defence(self):
        raise NotImplementedError
    def evaluate(self):
        raise NotImplementedError