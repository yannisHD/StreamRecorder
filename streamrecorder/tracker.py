'''
To get statistics call StreamManagerTracker.get_stats()

The return dictionary will be formated as follows:
    
dvrName: DVR Name
currentTime: Current time as datetime object
storageDeviceCount: number of devices available (0 if not on a pi)
usedStorageDeviceCount: number of devices containing video (0 if not on a pi)
totalStorage: total amount of storage in all file storage locations
freeStorage: amount of available storage for video
usedStorage: amount of storage used (not necessarily by video)
rootStorage: amount of storage available in root directory
streamCount: number of streams
totalFileCount: current number of video files in all streams(deleting files will decrease this number)
averageFileSize: average size of files for all streams
recordingFileCount: number of files being recorded to (also number of streams recording since streams record 0 or 1 files)
voltage: the voltage being recorded from the sensor (None if there is no sensor)
streams: dictionary containing info about each stream with each key being the stream name

Stream dictionary:
    fileCount: number of files for that stream
    avgSize: average size of a file for that stream
    filesRecording: number of files being recorded to (0 or 1)
    lastFile: the name of most recent complete file
    lastFileSize: size of the most recent complete file
    currentFile: the name of the file being recorded to
    currentFileSize: the size of the file being recorded to
'''

import time
import os

from streamrecorder import dvrutils
from streamrecorder import voltmeter

class StreamManagerTracker(object):
    
    def __init__(self, manager, logger):
        self.manager = manager
        self.dvrName = manager.dvrName
        self.logger = logger
        self.voltmeter = voltmeter.Voltmeter(logger)
    
    def get_stream_info(self, recorder):
        stats = {}
        stats['fileCount'] = sum(1 if recorder.recordingName in f else 0 for f in os.listdir(recorder.storagePath))
        stats['avgSize'] = recorder.get_avg_file_size()
        stats['currentFile'] = recorder.currentFile
        if recorder.createFilename and recorder.isRecording:
            stats['filesRecording'] = 1
            try:
                stats['currentFileSize'] = os.stat(os.path.join(recorder.storagePath, recorder.currentFile)).st_size
            except:
                stats['currentFileSize'] = 'ERROR'
        else:
            stats['filesRecording'] = 0
            stats['currentFileSize'] = 0
        stats['lastFile'] = recorder.lastFile
        if recorder.lastFile != None:
            try:
                stats['lastFileSize'] = os.stat(os.path.join(recorder.storagePath, recorder.lastFile)).st_size
            except:
                stats['lastFileSize'] = 'ERROR'
        else:
            stats['lastFileSize'] = 0
        return stats

    def directory_contains_video(self, path):
        if path[-1] == '/':
            path = path[:-1]
        recordingPrefix = '{}_{}'.format(self.dvrName, path.split('/')[-1]) # last part of path is stream name
        for f in os.listdir(path):
            if recordingPrefix in f:
                return True
        return False
    
    def get_usb_directories(self, path='/media/usb'):
        usbPaths = []
        i = 0
        while os.path.exists(path+str(i)):
            if os.path.ismount(path+str(i)):
                usbPaths.append(path+str(i))
            i += 1
        return usbPaths
            
    def get_usb_storage_info(self):
        stats = {}
        usbDirs = self.get_usb_directories()
        usedDirs = 0
        for d in usbDirs:
            for f in os.listdir(d):
                f = os.path.join(d, f)
                if os.path.isdir(f) and self.directory_contains_video(f):
                    usedDirs += 1
                    break
        stats['usedStorageDeviceCount'] = usedDirs
        totalStorage, freeStorage = 0, 0
        for d in usbDirs:
            s = os.statvfs(d)
            totalStorage += s.f_blocks * s.f_frsize
            freeStorage += s.f_bavail * s.f_frsize
        rootStorageStats = os.statvfs('/')
        stats['rootStorage'] = rootStorageStats.f_bavail * rootStorageStats.f_frsize
        stats['storageDeviceCount'] = len(usbDirs)
        stats['totalStorage'] = totalStorage
        stats['freeStorage'] = freeStorage
        stats['usedStorage'] = totalStorage - freeStorage
        return stats
    
    def get_nonusb_storage_info(self):
        stats = {}
        rootStorageStats = os.statvfs('/')
        stats['rootStorage'] = rootStorageStats.f_bavail * rootStorageStats.f_frsize
        stats['storageDeviceCount'] = 0
        stats['usedStorageDeviceCount'] = 0
        streamStats = os.statvfs(self.manager.storagePath)
        stats['totalStorage'] = streamStats.f_blocks * streamStats.f_frsize
        stats['freeStorage'] = streamStats.f_bavail * streamStats.f_frsize
        stats['usedStorage'] = stats['totalStorage'] - stats['freeStorage']
        return stats
    
    def get_stats(self):
        stats = {}
        stats['dvrName'] = self.dvrName
        stats['currentTime'] = time.strftime('%Y-%m-%d %H:%M:%S')
        if dvrutils.storage_is_usb(self.manager.storagePath):
            stats.update(self.get_usb_storage_info())
        else:
            stats.update(self.get_nonusb_storage_info())
        streams = {}
        for name, recorder in self.manager.processes.items():
            streams[name] = self.get_stream_info(recorder)
        stats['streams'] = streams
        stats['totalFileCount'] = sum(info['fileCount'] for name, info in streams.items())
        stats['recordingFileCount'] = sum(info['fileCount'] for name, info in streams.items())
        if stats['totalFileCount'] != 0:
            stats['avgFileSize'] =  sum(info['fileCount']*info['avgSize'] for name, info in streams.items()) / stats['totalFileCount']
        else:
            stats['avgFileSize'] = 0
        stats['streamCount'] = len(self.manager.processes)
        stats['voltage'] = self.voltmeter.get_voltage()
        return stats
