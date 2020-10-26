#usage : python split_folder.py

import os
import numpy as np
import shutil

# # Creating Train / Val / Test folders (One time use)
root_dir = 'lakh_tx1'

if not os.path.isdir(root_dir + '/train'):
    os.makedirs(root_dir +'/train')
if not os.path.isdir(root_dir +'/valid'):
    os.makedirs(root_dir +'/valid')

# Creating partitions of the data after shuffeling
src = "lakh_txt" # Folder to copy images from

allFileNames = os.listdir(src)
np.random.shuffle(allFileNames)
allFiles = np.array(allFileNames)
val_FileNames = allFiles[:10000]
train_FileNames = allFiles[10000:]
# train_FileNames, val_FileNames = np.split(np.array(allFileNames),
#                                                           [int(len(allFileNames)*0.95)])


train_FileNames = [src+'/'+ name for name in train_FileNames.tolist()]
val_FileNames = [src+'/' + name for name in val_FileNames.tolist()]

print('Total images: ', len(allFileNames))
print('Training: ', len(train_FileNames))
print('Validation: ', len(val_FileNames))

# Copy-pasting images
for name in train_FileNames:
    shutil.copy(name, root_dir+'/train')

for name in val_FileNames:
    shutil.copy(name, root_dir+'/val')
