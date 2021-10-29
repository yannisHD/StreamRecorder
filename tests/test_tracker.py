import os
import pytest
import shutil
import sys
import time

from unittest import mock

sys.path.append('..')

from streamrecorder import tracker

def logger():
    loggerMock = mock.Mock()
    return loggerMock

def recorder_mock(num):
    recorderMock = mock.Mock()
    recorderMock.recordingName = 'dvrName_unitTestStream{}'.format(num)
    recorderMock.get_avg_file_size.return_value = 100
    recorderMock.currentFile = None
    recorderMock.storagePath = 'storage/unitTestStream{}'.format(num)
    recorderMock.createFilename = True
    recorderMock.isRecording = False
    recorderMock.lastFile = None
    return recorderMock

@pytest.fixture
def create_tracker():
    if os.path.exists('storage'):
        shutil.rmtree('storage')
    os.mkdir('storage')
    os.mkdir('storage/unitTestStream0')
    os.mkdir('storage/unitTestStream1')
    storagePath = os.path.abspath('storage')
    managerMock = mock.Mock()
    managerMock.dvrName = 'dvrName'
    managerMock.storagePath = storagePath
    managerMock.processes = {'unitTestStream0' : recorder_mock(0),
                             'unitTestStream1' : recorder_mock(1)}
    return tracker.StreamManagerTracker(managerMock, logger())

def test_ctor(create_tracker):
    infoTrack = create_tracker
    assert infoTrack.manager != None
    assert infoTrack.dvrName == 'dvrName'
    
def test_get_stream_info(create_tracker):
    smTracker = create_tracker
    info = smTracker.get_stream_info(smTracker.manager.processes['unitTestStream0'])
    assert info['fileCount'] == 0
    assert info['avgSize'] == 100
    assert info['currentFile'] == None
    assert info['currentFileSize'] == 0
    assert info['filesRecording'] == 0
    assert info['currentFileSize'] == 0
    assert info['lastFile'] == None
    assert info['lastFileSize'] == 0
    with open('storage/unitTestStream0/old.txt', 'w') as f:
        f.write('Words')
    with open('storage/unitTestStream0/dvrName_unitTestStream0-20180101_000000-010000.txt', 'w') as f:
        f.write('Words')
    smTracker.manager.processes['unitTestStream0'].currentFile = 'dvrName_unitTestStream0-20180101_000000-010000.txt'
    smTracker.manager.processes['unitTestStream0'].lastFile = 'old.txt'
    smTracker.manager.processes['unitTestStream0'].isRecording = True
    newInfo = smTracker.get_stream_info(smTracker.manager.processes['unitTestStream0'])
    assert newInfo['fileCount'] == 1
    assert newInfo['currentFile'] == 'dvrName_unitTestStream0-20180101_000000-010000.txt'
    assert newInfo['currentFileSize'] > 0
    assert newInfo['lastFile'] == 'old.txt'
    assert newInfo['lastFileSize'] > 0
    assert newInfo['filesRecording'] == 1
    
def test_directory_contains_video(create_tracker):
    track = create_tracker
    assert track.directory_contains_video(os.path.abspath('storage/unitTestStream0')) == False
    file = open('storage/unitTestStream0/dvrName.txt', 'w')
    file.close()
    assert track.directory_contains_video(os.path.abspath('storage/unitTestStream0')) == False
    file = open('storage/unitTestStream0/dvrName_unitTestStream0-20180101_000000-010000.txt', 'w')
    file.close()
    assert track.directory_contains_video(os.path.abspath('storage/unitTestStream0')) == True
    
@mock.patch('os.path.exists')
@mock.patch('os.path.ismount')
def test_get_usb_directories(ismountMock, existsMock, create_tracker):
    
    def new_func(path):
        if int(path[-1]) < 3:
            return True
        return False
    
    ismountMock.side_effect = new_func
    existsMock.side_effect = new_func
    usbDirs = create_tracker.get_usb_directories()
    assert '/media/usb' in usbDirs[0]

@mock.patch.object(tracker.StreamManagerTracker, 'get_usb_directories')
@mock.patch('os.statvfs')
def test_get_usb_storage_info(statvfsMock, getUsbMock, create_tracker):
    
    def new_statvfs(path):
        infoMock = mock.Mock()
        infoMock.f_frsize = 10
        if path == 'storage':
            infoMock.f_blocks = 200
            infoMock.f_bavail = 150
        else:
            infoMock.f_blocks = 50
            infoMock.f_bavail = 30
        return infoMock
    
    getUsbMock.return_value = ['storage']
    
    statvfsMock.side_effect = new_statvfs
    smTracker = create_tracker
    info = smTracker.get_usb_storage_info()
    assert info['usedStorageDeviceCount'] == 0
    assert info['storageDeviceCount'] == 1
    assert info['rootStorage'] == 300
    assert info['totalStorage'] == 2000
    assert info['freeStorage'] == 1500
    assert info['usedStorage'] == 500
    file = open('storage/unitTestStream0/dvrName_unitTestStream0-20180101_000000-010000.txt', 'w')
    file.close()
    assert smTracker.get_usb_storage_info()['usedStorageDeviceCount'] == 1

@mock.patch('os.statvfs')    
def test_get_nonusb_storage_info(statvfsMock, create_tracker):

    def new_statvfs(path):
        infoMock = mock.Mock()
        infoMock.f_frsize = 10
        if path == 'storage':
            infoMock.f_blocks = 200
            infoMock.f_bavail = 150
        else:
            infoMock.f_blocks = 50
            infoMock.f_bavail = 30
        return infoMock    

    statvfsMock.side_effect = new_statvfs
    smTracker = create_tracker
    info = smTracker.get_nonusb_storage_info()
    assert info['rootStorage'] == 300
    assert info['storageDeviceCount'] == 0
    assert info['usedStorageDeviceCount'] == 0
    assert info['totalStorage'] == 500
    assert info['freeStorage'] == 300
    assert info['usedStorage'] == 200
    
def test_get_stats(create_tracker):
    smTracker = create_tracker
    with open('storage/unitTestStream0/old.txt', 'w') as f:
        f.write('Words')
    with  open('storage/unitTestStream0/dvrName_unitTestStream0-20180101_000000-010000.txt', 'w') as f:
        f.write('Words')
    info = smTracker.get_stats()
    assert time.strftime('%Y-%m-%d') in info['currentTime']
    assert info['dvrName'] == 'dvrName'
    assert 'streams' in info
    assert 'unitTestStream0' in info['streams']
    assert 'unitTestStream1' in info['streams']
    assert info['totalFileCount'] == 1
    assert info['avgFileSize'] == 100.0
    assert info['streamCount'] == 2