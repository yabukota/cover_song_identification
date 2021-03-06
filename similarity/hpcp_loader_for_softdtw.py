import os,sys
from torchvision import transforms
import torch, torch.utils
import numpy as np
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import random
import bisect


def cut_data(data, out_length, is_random=True, how=None):
    # 从data中随机切长度为out_length的一段
    # data: [f, t]
    # how: (str) random semi-random front
    if out_length is not None:
        if data.shape[1] > out_length:
            if is_random:
                max_offset = data.shape[1] - out_length
                if how == 'random':
                    offset = np.random.randint(max_offset)
                elif how[0:11] == 'semi-random':
                    cut_every = int(how.split('-')[-1])
                    offset = np.random.randint(max_offset)//cut_every*cut_every
                elif how == 'front':
                    offset = 0
                data = data[:, offset:(out_length+offset)]
            else:
                data = data[:, :out_length]
        else:
            offset = out_length - data.shape[1]
            data = np.pad(data, ((0,0),(0,offset)), "constant")
    if data.shape[1] < 150:
        offset = 150 - data.shape[1]
        data = np.pad(data, ((0,0),(0,offset)), "constant")
    return data


def cut_data_front(data, out_length):
    # 从data中从t=0处，切长度为out_length的一段
    # data: [f, t]
    if out_length is not None:
        if data.shape[1] > out_length:
            offset = 0
            data = data[:, offset:(out_length+offset)]
        else:
            offset = out_length - data.shape[1]
            data = np.pad(data, ((0,0),(0,offset)), "constant")
    if data.shape[1] < 200:
        offset = 200 - data.shape[1]
        data = np.pad(data, ((0,0),(0,offset)), "constant")
    return data


# 训练用的dataloader
class triplet_CQT(Dataset):
    # dataset: SHS100K
    def __init__(self, out_length, mode, cut,
                 is_random=True, is_label=False):
        '''
        mode: (datatype, length)
            datatype: 'cqt' 'f0' 'multif0'
            length: 'short' 'middle' 'long' .etc
        cut: 'front' 'random' 'semi-random-200'.etc
        '''
        if mode[0] in ['f0', 'multif0']:
            in_dir = f'/S3/DAA/gdoras_dataset/train/{mode[0]}_cqts_padded_1937x72/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/gdoras_train_triplet_{mode[1]}.list'
        elif mode[0] == 'cqt':
            in_dir = '/S3/DAA/jcy/SCNN/data/youtube_cqt_npy/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/triplet_SHS100K-TRAIN_{mode[1]}.list'
        elif mode[0] == 'multif0_avg5':
            dtype, avg = mode[0].split('_')
            in_dir = f'/S3/DAA/gdoras_dataset/{avg}/train/{dtype}_cqts_padded_1937x72/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/gdoras_train_triplet_{mode[1]}.list'
        
        self.datatype = mode[0]
        
        self.indir = in_dir
        self.out_length = out_length
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.is_random = is_random
        self.is_label = is_label
        self.cut = cut

    def __getitem__(self, index):
        filename = self.file_list[index].strip() # '1_1,1_2,3_1'
        name_list = filename.split(',')
        data_list = []
        for name in name_list: # name: 'a_b'
            version_id = int(name.split('_')[0])
            if self.datatype == 'f0':
                file_id = name.split('_')[1]
                data = np.load(self.indir+file_id+'.f0_cqt.npy') # [f, t]
            elif self.datatype in ['multif0', 'multif0_avg5']:
                file_id = name.split('_')[1]
                data = np.load(self.indir+file_id+'.multif0_cqt.npy') # [f, t]
            elif self.datatype == 'cqt':
                data = np.load(self.indir+name+'.npy') # [f, t]
            data = cut_data(data, self.out_length, self.is_random, self.cut)
            data = torch.from_numpy(data).float().unsqueeze(0)
            data_list.append(data)
            data_list.append(version_id)
        if self.is_label:
            return data_list[0], data_list[2], data_list[4], data_list[1], data_list[3], data_list[5]
        else:
            return data_list[0], data_list[2], data_list[4]

    def __len__(self):
        return len(self.file_list)

    

# 验证用的dataloader
class CQT(Dataset):
    def __init__(self, mode, out_length=None):
        '''
        mode: (dataset, datatype, length)
            dataset: 'train' 'val' 'test' 'songs350' 'songs80' 'new80' 'Mazurkas' 'gdoras_train' 'gdoras_test'
            datatype: 'f0' 'multif0' 'cqt'
            length: 'short' 'middle' 'long' .etc
        '''
        self.indir = '/S3/DAA/jcy/SCNN/data/youtube_cqt_npy/'
        self.mode = mode
        filepath = None
        if mode[0] == 'train':
            filepath = '/S3/DAA/jcy/SCNN/hpcp/SHS100K-TRAIN_6' # 不知道什么情况，先不管
        elif mode[0] == 'val':
            filepath = '/S3/DAA/jcy/SCNN/hpcp/SHS100K-VAL'
        elif mode[0] == 'test':
            filepath = '/S3/DAA/jcy/SCNN/hpcp/SHS100K-TEST'
        elif mode[0] == 'songs350':
            self.indir = '/S3/DAA/jcy/SCNN/data/you350_cqt_npy/'
            filepath = '/S3/DAA/jcy/SCNN/hpcp/you350_list.txt'
        elif mode[0] == 'songs80':
            self.indir = '/S3/DAA/jcy/SCNN/data/covers80_cqt_npy/'
            filepath = '/S3/DAA/jcy/SCNN/hpcp/songs80_list.txt'
        elif mode[0] == 'songs2000':
            self.indir = '/S3/DAA/jcy/SCNN/data/songs2000_cqt_npy/'
            filepath = '/S3/DAA/jcy/SCNN/hpcp/songs2000_list.txt'
        elif mode[0] == 'new80':
            self.indir = '/S3/DAA/jcy/SCNN/data/songs2000_cqt_npy/'
            filepath = '/S3/DAA/jcy/SCNN/hpcp/new80_list.txt'
        elif mode[0] == 'Mazurkas':
            self.indir = '/S3/DAA/jcy/SCNN/data/Mazurkas_cqt_npy/'
            filepath = '/S3/DAA/jcy/SCNN/hpcp/Mazurkas_list.txt'
        elif mode[0] == 'gdoras_train':
            if mode[1] == 'f0':
                self.indir = '/S3/DAA/gdoras_dataset/train/f0_cqts_padded_1937x72/'
            elif mode[1] == 'multif0':
                self.indir = '/S3/DAA/gdoras_dataset/train/multif0_cqts_padded_1937x72/'
            elif mode[1] == 'multif0_avg5':
                dtype, avg = mode[1].split('_')
                self.indir = f'/S3/DAA/gdoras_dataset/{avg}/train/{dtype}_cqts_padded_1937x72/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/gdoras_train_{mode[2]}.list'
        elif mode[0] == 'gdoras_test':
            if mode[1] == 'f0':
                self.indir = '/S3/DAA/gdoras_dataset/avg20/test/f0_cqts_padded_1937x72/'
            elif mode[1] == 'multif0':
                self.indir = '/S3/DAA/gdoras_dataset/avg20/test/multif0_cqts_padded_1937x72/'
            elif mode[1] == 'multif0_avg5':
                dtype, avg = mode[1].split('_')
                self.indir = f'/S3/DAA/gdoras_dataset/{avg}/test/{dtype}_cqts_padded_1937x72/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/gdoras_test_{mode[2]}.list'
        elif mode[0] == 'shs_wxy':
            self.indir = '/S3/DAA/jcy/SCNN/data/youtube_cqt_npy/'
            filepath = f'/S3/DAA/wxy/cover_song_identification/similarity/list/shs100k_{mode[2]}.list'
        
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length

    def __getitem__(self, index):
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('_')
        # set_id, version_id = int(set_id), int(version_id)
        if self.mode[1] == 'f0':
            in_path = self.indir + version_id + '.f0_cqt.npy'
        elif self.mode[1] in ['multif0', 'multif0_avg5']:
            in_path = self.indir + version_id + '.multif0_cqt.npy'
        elif self.mode[1] == 'cqt':
            in_path = self.indir + filename + '.npy'
        data = np.load(in_path) # [f, t]
        if self.mode[0] == 'train':
            data = cut_data(data, self.out_length)  # [f, t=84]
        else:
            data = cut_data_front(data, self.out_length)
        data = torch.from_numpy(data).float().unsqueeze(0)
        return data, int(set_id)

    def __len__(self):
        return len(self.file_list)





'''
class CQT_cut_test(Dataset):
    def __init__(self, mode='train', out_length=None):
        self.indir = 'data/youtube_cqt_npy/'
        self.mode = mode
        if mode == 'train':
            filepath = 'hpcp/SHS100K-TRAIN_6' # sid_vid
        elif mode == 'val':
            # filepath='hpcp/val_list.txt'
            filepath = 'hpcp/SHS100K-VAL' # sid_vid
        elif mode == 'test':
            filepath = 'hpcp/SHS100K-TEST' # sid_vid
            # filepath='hpcp/test_list.txt'
        elif mode == 'songs350':
            self.indir = 'data/you350_cqt_npy/'
            filepath = 'hpcp/you350_list.txt'
        elif mode == 'songs80':
            self.indir = 'data/covers80_cqt_npy/'
            filepath = 'hpcp/songs80_list.txt'
        elif mode == 'songs2000':
            self.indir = 'data/songs2000_cqt_npy/'
            filepath = 'hpcp/songs2000_list.txt'
        elif mode == 'new80':
            self.indir = 'data/songs2000_cqt_npy/'
            filepath = 'hpcp/new80_list.txt'
        elif mode == 'Mazurkas':
            self.indir = 'data/Mazurkas_cqt_npy/'
            filepath = 'hpcp/Mazurkas_list.txt'
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length

    def __getitem__(self, index):
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('.')[0].split('_')
        set_id, version_id = int(set_id), int(version_id)
        in_path = self.indir + filename + '.npy'
        data = np.load(in_path)  # from 12xN to Nx12
        data = data.T
        # Cut to 394
        if self.mode == 'train':
            data = cut_data_test(data, self.out_length)  # L, 84
        else:
            data = cut_data_front_test(data, self.out_length)
        # 12 to 23
        data = torch.from_numpy(data).float()
        # data = torch.from_numpy(data[:,0:-13] ).float()
        data = data.permute(1, 0).unsqueeze(0)
        
        # data = torch.cat((data,torch.cat([data[:,0:36,:], data[:,0:35,:]],dim=1)))
        # if self.mode == 'train':
        #    set_id = self.new_map[set_id]
        return data, int(set_id)

    def __len__(self):
        return len(self.file_list)
'''




'''
class HPCP(Dataset):
    def __init__(self, mode='train', out_length=None):
        self.indir = 'data/youtube_hpcp_npy/'
        if mode=='train': filepath='hpcp/train_list_6.txt'
        elif mode == 'val':
            filepath='hpcp/val_list.txt'
        elif mode == 'songs350': 
            self.indir = 'data/you350_hpcp_npy/'
            filepath='hpcp/you350_list.txt'
        elif mode == 'test': filepath='hpcp/hpcp_test_list.txt'
        elif mode == 'songs80': 
            self.indir = 'data/80_hpcp_npy/'
            filepath = 'hpcp/songs80_list.txt'
        elif mode == 'songs2000': 
            self.indir = 'data/songs2000_hpcp_npy/'
            filepath = 'hpcp/songs2000_list.txt'
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length
    def __getitem__(self, index):
        # data shape is [394, 23]
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('.')[0].split('_')
        set_id, version_id = int(set_id), int(version_id)
        in_path = self.indir+filename+'.npy'
        data = np.load(in_path)
        # Cut to 394
        data = cut_data(data, self.out_length)
        # 12 to 23
        data = torch.from_numpy(np.concatenate((data, data[:,0:-1]), axis=1))
        data = data.permute(1,0).unsqueeze(0)
        return data, set_id 
    def __len__(self):
        return len(self.file_list)

'''
    

'''
class triplet_HPCP(Dataset):
    
    def __init__(self, out_length):
        self.indir = 'data/youtube_hpcp_npy/'
        filepath = 'hpcp/triplet_hpcp_list.txt'
        self.out_length = out_length
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
            
    def __getitem__(self, index):
        filename = self.file_list[index].strip()
        name_list = filename.split(',')
        data_list = []
        for name in name_list:
            data = np.load(self.indir+name+'.npy')
            data = cut_data(data, self.out_length)
            data = torch.from_numpy(np.concatenate((data, data[:,0:-1]), axis=1))
            data = data.permute(1,0).unsqueeze(0)
            data_list.append(data) 
        return data_list[0], data_list[1], data_list[2]
    
    def __len__(self):
        return len(self.file_list)
'''

    
'''
class triplet_CQT_test(Dataset):
    
    def __init__(self, out_length, in_dir='data/youtube_cqt_npy/', filepath='hpcp/triplet_SHS100K-TRAIN.list', is_random=True, is_label=False):
        self.indir = in_dir
        self.out_length = out_length
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.is_random = is_random
        self.is_label = is_label

    def __getitem__(self, index):
        filename = self.file_list[index].strip()
        name_list = filename.split(',')
        data_list = []
        for name in name_list:
            version_id = int(name.split('_')[0])
            data = np.load(self.indir+name+'.npy')
            data = data.T
            data = cut_data_test(data, self.out_length, self.is_random)
            data = torch.from_numpy(data).float()
            data = data.permute(1, 0).unsqueeze(0)
            data_list.append(data)
            data_list.append(version_id)
        if self.is_label:
            return data_list[0], data_list[2], data_list[4], data_list[1], data_list[3], data_list[5]
        else:
            return data_list[0], data_list[2], data_list[4]

    def __len__(self):
        return len(self.file_list)

    
class CENS(Dataset):
    
    def __init__(self, mode='train', out_length=None):
        self.indir = 'data/youtube_cens_npy/'
        if mode=='train': 
            filepath='hpcp/hpcp_train_list.txt'
        elif mode == 'val':
            filepath='hpcp/val_list.txt'
        elif mode == 'songs350': 
            self.indir = 'data/you350_cens_npy/'
            filepath='hpcp/you350_list.txt'
        elif mode == 'test': 
            filepath='hpcp/hpcp_test_list.txt'
        elif mode == 'songs80': 
            self.indir = 'data/covers80_cens_npy/'
            filepath = 'hpcp/songs80_list.txt'
        #elif mode == 'songs2000': 
        #    self.indir = 'data/songs2000_hpcp_npy/'
        #    filepath = 'hpcp/songs2000_list.txt'
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length
        
    def __getitem__(self, index):
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('.')[0].split('_')
        set_id, version_id = int(set_id), int(version_id)
        in_path = self.indir+filename+'.npy'
        data = np.load(in_path) # from 12xN to Nx12
        data = data.T
        # Cut to 394
        data = cut_data(data, self.out_length)
        # 12 to 23
        data = torch.from_numpy(np.concatenate((data, data[:, 0:-1]), axis=1)).float()
        data = data.permute(1,0).unsqueeze(0)
        return data, set_id
    
    def __len__(self):
        return len(self.file_list)
        
        
def cut_data_test(data, out_length, is_random=True):
    if out_length is not None:
        if data.shape[0] > out_length:
            if is_random:
                max_offset = data.shape[0] - out_length
                offset = np.random.randint(max_offset)
                data = data[offset:(out_length+offset),:]
            else:
                data = data[:out_length, :]
        else:
            offset = out_length - data.shape[0]
            if offset <= data.shape[0]:
                temp = data[:offset, :]
                data = np.concatenate((temp, data), 0)
            else:
                beta = offset // data.shape[0]
                res = offset % data.shape[0]
                temp = data
                for i in range(beta):
                    temp = np.concatenate((temp, data), 0)
                temp2 = data[:res, :]
                data = np.concatenate((temp, temp2), 0)
    if data.shape[0] < 150:
        offset = 150 - data.shape[0]
        temp = data[:offset, :]
        data = np.concatenate(( temp,data), 0)
    return data

    
def cut_data_front_test(data, out_length):
    if out_length is not None:
        if data.shape[0] > out_length:
            max_offset = data.shape[0] - out_length
            #offset = np.random.randint(max_offset)
            offset = 0
            data = data[offset:(out_length+offset),:]
        else:
            offset = out_length - data.shape[0]
            if offset <= data.shape[0]:
                temp = data[:offset, :]
                data = np.concatenate((temp, data), 0)
            else:
                beta = offset//data.shape[0]
                res  = offset%data.shape[0]
                temp = data
                for i in range(beta):
                        temp = np.concatenate((temp, data), 0)
                temp2 = data[:res, :]
                data = np.concatenate((temp, temp2), 0)
    if data.shape[0] < 150:
        offset = 150 - data.shape[0]
        temp = data[:offset, :]
        data = np.concatenate(( temp,data), 0)
    return data    
'''

        
'''        
class CQT_test(Dataset):
    def __init__(self, mode='key_6', out_length=None):
        #self.indir = 'data/youtube_cqt_npy/'
        self.indir = 'data/youtube_cqt_npy/'
        self.mode=mode
        filepath = 'hpcp/songs80_list.txt'
        if mode == 'key_6':
            self.indir = 'covers80_cqt_npy/covers80_key6_cqt_npy/'
        elif mode =='key_n6':
            self.indir = 'covers80_cqt_npy/covers80_keyn6_cqt_npy/'
        elif mode =='key_12':
            self.indir = 'covers80_cqt_npy/covers80_key12_cqt_npy/'
        elif mode =='key_n12':
            self.indir = 'covers80_cqt_npy/covers80_keyn12_cqt_npy/'
        elif mode == 'tempo08':
            self.indir = 'covers80_cqt_npy/covers80_tempo08_cqt_npy/'
        elif mode == 'tempo09':
            self.indir = 'covers80_cqt_npy/covers80_tempo09_cqt_npy/'
        elif mode == 'tempo11':
            self.indir = 'covers80_cqt_npy/covers80_tempo11_cqt_npy/'
        elif mode == 'tempo12':
            self.indir = 'covers80_cqt_npy/covers80_tempo12_cqt_npy/'
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length
    def __getitem__(self, index):
        transform_train = transforms.Compose([
            lambda x : x.T,
            lambda x : change_speed(x, 0.7, 1.3),
            #lambda x : x-np.mean(x),
            lambda x : x.astype(np.float32) / (np.max(np.abs(x))+ 1e-6),
            lambda x : cut_data(x, self.out_length),
            lambda x : torch.Tensor(x),
            lambda x : x.permute(1,0).unsqueeze(0),
        ])
        transform_test = transforms.Compose([
            lambda x : x.T,
            #lambda x : x-np.mean(x),
            lambda x : x.astype(np.float32) / (np.max(np.abs(x))+ 1e-6),
            lambda x : cut_data_front(x, self.out_length),
            lambda x : torch.Tensor(x),
            lambda x : x.permute(1,0).unsqueeze(0),
        ])
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('.')[0].split('_')
        set_id, version_id = int(set_id), int(version_id)
        in_path = self.indir+filename+'.npy'
        data = np.load(in_path) # from 12xN to Nx12
        
#         data = data.T
#         # Cut to 394
#         if self.mode is 'train':
#             data = change_speed(data, 0.7, 1.3)
#             data = cut_data(data, self.out_length) # L, 84
#         else :
#             data = cut_data_front(data, self.out_length)
#         # 12 to 23
#         data = data / (np.max(np.abs(data))+ 1e-6) # rescale to -1 to 1
#         data = torch.from_numpy(data ).float()
#         data = data.permute(1,0).unsqueeze(0)

        if self.mode == 'train':
            data = transform_train(data)
        else:
            data = transform_test(data)
        return data, int(set_id)
    def __len__(self):
        return len(self.file_list)
'''
    
    
'''
class CQT_nocut(Dataset):
    def __init__(self, mode='train', out_length=None):
        # self.indir = 'data/youtube_cqt_npy/'
        self.indir = 'data/youtube_cqt_npy/'
        self.mode = mode
        if mode == 'train':
            # filepath='hpcp/hpcp_train_list.txt'
            filepath = 'hpcp/SHS100K-TRAIN_6'
            # filepath='hpcp/train_list_6.txt'
            # self.new_map=np.load('hpcp/new_map.npy')
        elif mode == 'val':
            # filepath='hpcp/val_list.txt'
            filepath = 'hpcp/SHS100K-VAL'
        elif mode == 'songs350':
            self.indir = 'data/you350_cqt_npy/'
            filepath = 'hpcp/you350_list.txt'
        elif mode == 'test':
            filepath = 'hpcp/SHS100K-TEST'
            # filepath='hpcp/test_list.txt'
        elif mode == 'songs80':
            self.indir = 'data/covers80_cqt_npy/'
            filepath = 'hpcp/songs80_list.txt'
        elif mode == 'songs2000':
            self.indir = 'data/songs2000_cqt_npy/'
            filepath = 'hpcp/songs2000_list.txt'
        elif mode == 'new80':
            self.indir = 'data/songs2000_cqt_npy/'
            filepath = 'hpcp/new80_list.txt'
        elif mode == 'Mazurkas':
            self.indir = 'data/Mazurkas_cqt_npy/'
            filepath = 'hpcp/Mazurkas_list.txt'
        with open(filepath, 'r') as fp:
            self.file_list = [line.rstrip() for line in fp]
        self.out_length = out_length

    def __getitem__(self, index):
        transform_train = transforms.Compose([
            lambda x: x.T,
            lambda x: x.astype(np.float32) / (np.max(np.abs(x)) + 1e-6),
            lambda x: cut_data(x, self.out_length),
            lambda x: torch.Tensor(x),
            lambda x: x.permute(1, 0).unsqueeze(0),
        ])
        transform_test = transforms.Compose([
            lambda x: x.T,
            lambda x: x.astype(np.float32) / (np.max(np.abs(x)) + 1e-6),
            lambda x: cut_data_front(x, self.out_length),
            lambda x: torch.Tensor(x),
            lambda x: x.permute(1, 0).unsqueeze(0),
        ])
        filename = self.file_list[index].strip()
        set_id, version_id = filename.split('.')[0].split('_')
        set_id, version_id = int(set_id), int(version_id)
        in_path = self.indir + filename + '.npy'
        data = np.load(in_path)  # from 12xN to Nx12

        if self.mode is 'train':
            data = transform_train(data)
        else:
            data = transform_test(data)
        return data, int(set_id)

    def __len__(self):
'''
        
'''
if __name__=='__main__':
    #train_dataset = HPCP('train', 394)
    #trainloader = torch.utils.data.DataLoader(train_dataset, batch_size=128, num_workers=12, shuffle=True)
    pass
'''