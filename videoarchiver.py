#!/usr/bin/python

"""A concise tool for archiving video as it is recorded.
"""
import os, time, argparse
import subprocess32 as subprocess
from socket import gethostname
import dvrutils

def read_archive_config(fName):
    with open(fName, 'r') as f:
        flines = f.readlines()
        
    streams = []        # [{'StreamName': <name>, 'VideoPath': <path>, 'ArchivePath': <path>},...]
    for line in flines:
        if line[0] != '#':      # ignore comment lines
            sName = line.split('#')[0].strip() if '#' in line else line.strip()
            if len(sName) > 0:
                streams.append({'StreamName': sName, 'VideoPath': '', 'ArchivePath': ''})
            
    return streams

class StreamArchiver:
    def __init__(self, logger, dvrName, streamListFile='videoarchiver.cfg', storagePath='/mnt/video', archivePath='/mnt/archive'):
        self.logger = logger
        self.dvrName = dvrName
        self.streamListFile = os.path.join(archivePath,streamListFile)
        self.storagePath = storagePath
        self.archivePath = archivePath
        if os.path.exists(self.streamListFile):
            self.streams = read_archive_config(self.streamListFile)
            self.check_directories()
        else:
            self.logger.error("The specified configuration file {} cannot be found!".format(self.streamListFile))
            
    def check_directories(self):
        # check which streams this computer has and make sure the directories are set up right
        goodStreams = []
        for s in self.streams:
            s['VideoPath'] = os.path.join(self.storagePath,s['StreamName'])
            
            if os.path.isdir(s['VideoPath']):       # if we have this stream
                #s['ArchivePath'] = os.path.join(self.archivePath,s['StreamName'])
                s['ArchivePath'] = self.archivePath
                if not os.path.isdir(s['ArchivePath']):         # if the stream has no directory in the archive, then make it
                    if os.path.exists(s['ArchivePath']):
                        s['ArchivePath'] = dvrutils.get_unique_filename(s['ArchivePath'],nZeros=0)          # if there is a file with the same name for whatever reason, change the directory name
                    os.makedirs(s['ArchivePath'])
                    if self.logger is not None:
                        self.logger.info('Created directory {} for stream {}!'.format(s['ArchivePath'],s['StreamName']))
                goodStreams.append(s)
            else:       # if we don't, give a debug message for the user
                if self.logger is not None:
                    self.logger.debug("Ignoring stream {} as it does not exist on this system.".format(s['StreamName']))
        self.streams = goodStreams
    
    def sync_streams(self):
        # sync the streams one at a time to minimize fragmentation (NOTE: Eventually this will be pull-based, so there will be no fragmentation)
        for s in self.streams:
            # use rsync to perform the copy
            syncCmd = ['rsync', '-rlptg', s['VideoPath'], s['ArchivePath']]        # r = recurse; l = symlinks as symlinks; preserve: p = permissions, t = modification times, g = group
            if self.logger is not None:
                self.logger.info("Syncing video for stream {} in {} to archive at {}...".format(s['StreamName'], s['VideoPath'], s['ArchivePath']))
                self.logger.debug("Syncing with the command: {}".format(syncCmd))
            startTime = time.time()
            subprocess.call(syncCmd)
            elapsedTime = time.time() - startTime
            if self.logger is not None:
                self.logger.info("Sync for stream {} took {} seconds.".format(s['StreamName'], elapsedTime))
            
    def start_sync_daemon(self, timeOfDay='1:00'):
        # repeatedly sync streams on a schedule as determined by the timeOfDay parameter
        # timeOfDay is a time string in HH:MM format
        # by default it will sync at 1:00 AM every day
        try:
            syncHour, syncMin = [int(t) for t in timeOfDay.split(':')]
        except:
            syncHour, syncMin = 1, 0            # use default if the user input an incorrect time string
            self.logger.warning("Invalid time string: '{}'! Reverting to default! This is probably not what you wanted!".format(timeOfDay))
        
        self.logger.info("Going to sync daily at {}:{}".format(syncHour, syncMin))
        self.syncHistory = {int(time.strftime('%Y%m%d')): False}        # save a log to know if we have synced today or not
        while True:
            dayKey = int(time.strftime('%Y%m%d'))
            if dayKey not in self.syncHistory:                          # if this is a new day, put an entry in the log so we know that it's a new day and we need to watch for the sync time
                self.syncHistory.update({dayKey: False})
            
            if not self.syncHistory[dayKey]:                 # if we haven't synced yet today, check the time to see if we should
                currTime = time.localtime()
                syncNow = False
                if currTime.tm_hour > syncHour:
                    syncNow = True
                elif currTime.tm_hour == syncHour and currTime.tm_min >= syncMin:
                    syncNow = True
                
                if syncNow:                     # if we should, sync files and log the event
                    self.sync_streams()
                    self.syncHistory[dayKey] = True
            
            # if we already synced today, we don't need to do anything
            time.sleep(5)
            
if __name__ == "__main__":
    # parse any arguments passed in
    parser = argparse.ArgumentParser(prog='videoarchiver.py', usage='%(prog)s [configFilename]', description='Archives/backs up video from predefined camera streams to a defined location.')
    parser.add_argument('streamListFile', help = '(Optional) Name of the configuration file to defining streams to backup (defaults to archivePath/dvrName).')
    parser.add_argument('-t', '--time-of-day', dest = 'timeOfDay', default = '1:00', help = '(Optional) Time of day to perform the backup (HH:MM, 24-hour format) (default: %(default)s).')
    parser.add_argument('-l', '--log-file', dest = 'logFilename', default = 'videoarchiver.cfg', help = '(Optional) Name of the file for logging (default: %(default)s).')
    parser.add_argument('-v', '--loglevel', dest = 'loglevel', default = 'INFO', help = '(Optional) streamrecorder log level (does not affect FFMPEG log level). Specify numeric values (10, 20, 30, etc.) or strings like DEBUG or WARNING')
    parser.add_argument('-s', '--storage-path', dest = 'storagePath', default = '/mnt/video', help = '(Optional) Location of the archive directory (default: %(default)s).')
    parser.add_argument('-a', '--archive-path', dest = 'archivePath', default = '/mnt/archive', help = '(Optional) Location of the archive directory (default: %(default)s).')
    parser.add_argument('-d', '--dvr-name', dest = 'dvrName', default = gethostname(), help = '(Optional) Name of the computer recording the stream (defaults to hostname: %(default)s).')
    args = parser.parse_args()
    
    # setup logging
    logFilePath = os.path.join(args.archivePath, "{}.log".format(args.dvrName)) if args.logFilename is None else args.logFilename       # by default, log to file: archivePath/dvrName.log
    logger = dvrutils.setup_logging(logFilePath, args.loglevel, args.dvrName, logToFile=True, logToStdout=True)      # this function will output the loglevel for verification
    
    try:
        # create the archiver object, which makes sure things are set up correctly
        streamArchiver = StreamArchiver(logger, args.dvrName, args.streamListFile, args.storagePath, args.archivePath)
        
        # start the daemon
        streamArchiver.start_sync_daemon(args.timeOfDay)
    except:
        # if there was a crash, log it
        # TODO: send an email alert (once it works)
        logger.error("The program crashed unexpectedly!")
    