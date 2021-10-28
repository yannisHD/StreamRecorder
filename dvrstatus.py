#!/usr/bin/python

import os, sys, time, glob, argparse
import subprocess
import dvrutils, srconfig
from socket import gethostname

appDir = os.path.join(os.environ['HOME'],'streamrecorder')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the status of a computer running streamrecorder using the values defined in the various configuration files.")
    parser.add_argument('-f','--config', dest='configFile', help="Path to the master streamrecorder configuration file (for overriding the default).")
    parser.add_argument('-n','--num-files', dest='nRecentFiles', type=int, default=2, help="Number of most recent files to print information about (default: %(default)s).")
    parser.add_argument('--file-info-format', dest='fileInfoFormat', default="{:10s}{:s}", help="File info format specification.")
    args = parser.parse_args()
    
    # load the configuration
    cfg = srconfig.getConfig(args.configFile)
    
    # generate the report (text output)
    # start with system name and time
    deviceName = gethostname()
    statStr = "{} Status Report".format(deviceName)
    print statStr
    print "=" * len(statStr)
    print "System Time: {}".format(time.strftime('%c'))
    
    # print the storage usage using df
    print "\nStorage Usage:"
    print "=============="
    cmd = ['df','-h'] + ['/'] + cfg.storagePaths
    print subprocess.check_output(cmd)
    
    # now go through our streams, find the latest 2 files, and report their names and sizes
    print "\nRecording Stream Info"
    print "====================="
    for streamName in cfg.streamUrls.keys():
        streamUrl = cfg.streamUrls.get(streamName)
        
        # get all the files in all the storage paths for this stream
        videoFiles = []
        nDevices = 0
        for sp in cfg.storagePaths:
            streamPath = os.path.join(sp, streamName)
            if os.path.exists(streamPath):
                vfl = glob.glob(os.path.join(streamPath, '*.avi'))
                if len(vfl) > 0:
                    videoFiles.extend(vfl)
                    nDevices += 1
        
        # get the 2 newest files
        # first make a dict keyed on the times
        # NOTE - assumes no 2 files have the exact same modified time (unlikely within a single stream)
        fileTimes = {}
        for vf in videoFiles:
            mtime = os.path.getmtime(vf)
            fileTimes[mtime] = vf
        
        # now get up to the nRecentFiles latest keys
        sortedTimes = sorted(fileTimes.keys())
        lastTimes = sortedTimes[-min(args.nRecentFiles,len(sortedTimes)):] if len(sortedTimes) > 0 else []
        
        # get the files
        lastFiles = [fileTimes[t] for t in lastTimes]
        
        # print info about the files
        print streamName
        print '-' * len(streamName)
        print "{} files on {} storage devices".format(len(videoFiles), nDevices)
        
        if len(lastFiles) > 0:
            print "\nMost recent files:"
            print args.fileInfoFormat.format('Size','Filename')
            for f in lastFiles:
                # get the size of this file
                fsize = os.path.getsize(f)
                
                # make a string with the formatted file size and file path
                print args.fileInfoFormat.format(dvrutils.format_size(fsize),f)
    
        # output a frame from each stream (jpg, where should it go??)
        