#!/usr/bin/python

"""Classes and functions for managing streamrecorder configuration."""

import os, sys, argparse
import dvrutils, stream
from pgutils import cfgutils

homeDir = os.environ['HOME']
appDir = os.path.join(homeDir,'streamrecorder')

def pickConfigFile(basename, storageDir):
    """
    Retrieve the file with the given basename (name without the path), first
    checking storageDir, then homeDir, then appDir, returning the path of the
    first file that exists.
    """
    for pth in [storageDir, homeDir, appDir]:
        fpath = os.path.join(pth, basename)
        if os.path.exists(fpath):
            return fpath

def getConfig(configFilename=None, **kwargs):
    """
    Return the StreamrecorderConfig object created based on the info in the
    file at appDir/streamrecorder.cfg (or the path defined by configFilename).
    """
    configFilename = os.path.join(appDir, 'streamrecorder.cfg') if configFilename is None else configFilename
    return StreamrecorderConfig(configFilename, **kwargs)

class StreamrecorderConfig(cfgutils.ConfigObjConfig):
    """
    A class for encapsulating the streamrecorder config, including the master
    config, camera info config, and streams config in one namespace.
    """
    
    def parseConfig(self, cameraConfigFile=None, streamConfigFile=None, **kwargs):
        """Load the camera and stream config files."""
        # load the camera info
        self.cameraConfigFile = pickConfigFile(self.CamConfig, self.Storage.path) if cameraConfigFile is None else cameraConfigFile
        self.cameraInfo = cfgutils.ConfigObjConfig(self.cameraConfigFile)
        
        # load the stream info
        self.streamConfigFile = pickConfigFile(self.StreamConfig, self.Storage.path) if streamConfigFile is None else streamConfigFile
        self.streamInfo = cfgutils.ConfigObjConfig(self.streamConfigFile)
        
        # generate the stream URLs
        self.makeStreamUrls()
        
        # get list of storage paths
        self.checkStoragePaths()
    
    def checkStoragePaths(self):
        """
        Retrieve the full path(s) to any video storage. This will create a 
        list containing either the path in the Storage section of the main 
        config file, or a list of the mounted USB device paths if the storage
        path is /media/usb. The paths will be saved at self.storagePaths.
        """
        self.storagePaths = []
        if self.Storage.path.startswith('/media/usb'):
            for i in range(0,8):
                pth = "/media/usb{}".format(i)
                if os.path.ismount(pth):
                    self.storagePaths.append(pth)
        else:
            self.storagePaths.append(self.Storage.path)
    
    def makeStreamUrls(self):
        """
        Format the URL for each stream, saving them in a Bunch at 
        self.streamUrls, keyed on their stream names.
        """
        streamUrls = {}
        for sname in self.streamInfo.Streams.keys():
            strm = self.streamInfo.Streams.get(sname)
            streamUrls[sname] = self.formatStreamUrl(strm)
        self.streamUrls = cfgutils.Bunch(streamUrls)
    
    def formatStreamUrl(self, strm):
        """
        Return the URL to the video stream given the list of parameters strm 
        (a list of 3+ parameters as read from the streams.cfg file).
        """
        # IP address, manufacturer, stream type, schedule, options
        # we don't care about the schedule, just options if they are there
        ip, manufacturer, streamType, optStr = None, None, None, None
        if len(strm) == 3:
            ip, manufacturer, streamType = strm                     # record this stream with default schedule
        elif len(strm) == 5:
            ip, manufacturer, streamType, jnk, optStr = strm   # record this stream with the given schedule (which can be 'default') and options
        
        # if no credentials, take default from cameraInfo
        user = self.cameraInfo.DefaultUser
        passwd = self.cameraInfo.DefaultPasswd
        
        # look up stream info
        url = None
        if self.cameraInfo.has(manufacturer):
            # manufacturer is defined - check for user or passwd to override default
            manuSec = self.cameraInfo.get(manufacturer)
            if manuSec.has('user', caseSensitive=False):
                user = manuSec.get('user', caseSensitive=False)
            if manuSec.has('passwd', caseSensitive=False):
                passwd = manuSec.get('passwd', caseSensitive=False)
            
            # now check for this stream type
            if manuSec.has(streamType):
                # check if we need to override credentials
                streamSec = manuSec.get(streamType)
                if streamSec.has('user', caseSensitive=False):
                    user = streamSec.get('user', caseSensitive=False)
                if streamSec.has('passwd', caseSensitive=False):
                    passwd = streamSec.get('passwd', caseSensitive=False)
                
                # now finally get the URL if it is defined
                if streamSec.has('url', caseSensitive=False):
                    url = streamSec.get('url', caseSensitive=False)
        
        # finally see if we need to override user or passwd from options
        if optStr is not None:
            for o in optStr.strip().strip('()').split(';'):         # split on semicolons
                k,v = [oo.strip() for oo in o.strip().split('=')]
                if k.lower() == 'user':
                    user = v
                elif k.lower() == 'passwd':
                    passwd = passwd
        
        # assemble a CameraInfo object with the info we have, format the URL, and return it
        camInfo = stream.CameraInfo(manufacturer, streamType, user, passwd, url)
        return camInfo.format_url(ip)
    