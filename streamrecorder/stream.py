import os
import glob
import datetime
import time
import math
import operator
import logging
import re
import requests
import subprocess
import sys
import threading
import traceback
import pytz

sys.path.append('..')

from streamrecorder import schedule
from streamrecorder import dvrutils


class StreamManager(object):
    """A class for managing the recording of multiple streams from multiple IP streams simultaneously."""
    def __init__(self, dvrName, execPath, storagePath, mainLogger, logFilePath, logLevel='INFO', logLocation='../logs/',
                 overwriteFiles=False, minDaysOld=3, initTime=15, performRestarts=False, onvifDir=None, port=None):
        self.dvrName = dvrName
        self.execPath = execPath
        self.appDir = os.path.dirname(execPath)
        self.storagePath = storagePath
        self.logLocation = logLocation
        self.logLevel = logLevel
        self.logFilePath = logFilePath
        self.initTime = initTime
        self.performRestarts = performRestarts
        self.port = port
        self.overwriteFiles = overwriteFiles
        self.minDaysOld = minDaysOld
        self.processes = {}
        self.streamStarts = {}
        self.corruptedUSBs = []
        self.mainLogger = mainLogger
        self.storageFull = False
        self.onvifDir = onvifDir
        if onvifDir is not None:
            sys.path.append(onvifDir)

    #============================================================
    # Stream Managing Functions
    #------------------------------------------------------------
    def add_video_stream(self, streamName, streamURL, videoContainer, videoCodec, videoQuality, outputFrameRate,
                         recordingSchedule, ffmpegLogLevel='warning', usr=None, password=None, manu=None, ip=None):
        videoLocation = os.path.join(self.storagePath, streamName)
        if not os.path.exists(videoLocation):
            self.mainLogger.info("Folder {} does not exist. Creating it now!".format(videoLocation))
            os.makedirs(videoLocation)
        cr = CameraRecorder(self.dvrName, streamName, streamURL, videoContainer, videoCodec, videoQuality, outputFrameRate, recordingSchedule,
                            videoLocation, ffmpegLogLevel=ffmpegLogLevel, logLocation=self.logLocation, logLevel=self.logLevel, initTime=self.initTime,
                            performRestarts=self.performRestarts, user=usr, passwd=password, manufacturer=manu, ipAddr=ip, port=self.port, onvifDir=self.onvifDir)
        self.processes.update({streamName: cr})

    def add_command_stream(self, streamName, container, commandStr, recordingSchedule):
        path = os.path.join(self.storagePath, streamName)
        if not os.path.exists(path):
            self.mainLogger.info("Folder {} does not exist. Creating it now!".format(path))
            os.makedirs(path)
        cr = CommandRecorder(self.dvrName, streamName, path, container, commandStr, recordingSchedule, self.logLocation, self.logLevel)
        self.processes.update({streamName : cr})

    def start_streams(self):
        self.mainLogger.info("Starting {} streams".format(len(self.processes)))
        for name, stream in self.processes.items():
            stream.start_recording()

    def restart_logger(self):
        self.mainLogger = dvrutils.setup_logging(self.logFilePath, self.logLevel, self.dvrName,
                                                 logToFile=True, logToStdout=True, logToEmail=False, toaddrs=None)

    def check_available_storage(self, spaceNeeded=None): # returns true if storage full, false if not
        # get the available space
        self.mainLogger.debug("Checking storage space...")
        self.bytesFree = dvrutils.get_disk_usage(self.storagePath, mounted=False)                       # NOTE/TODO we don't care if it is mounted now, but will we ever?
        self.mainLogger.debug("{} space is available!".format(dvrutils.format_size(self.bytesFree)))

        # calculate the amount of space we will need for a round of recording
        if spaceNeeded is None:
            self.spaceNeeded = 0
            self.mainLogger.debug("Calculating storage requirements for the {} feeds being recorded...".format(len(self.processes)))
            for stream in self.processes.values():
                self.spaceNeeded += stream.get_avg_file_size(safetyFactor=1.5)
            self.mainLogger.debug("Need {} space to start next round of recording...".format(dvrutils.format_size(self.spaceNeeded)))
        else:
            self.spaceNeeded = spaceNeeded

        # format sizes as strings
        self.strSpaceNeeded = dvrutils.format_size(self.spaceNeeded)
        self.strBytesFree = dvrutils.format_size(self.bytesFree)
        return self.spaceNeeded > self.bytesFree

    def get_stream_size_order(self):
        # returns the streams in descending order by stream size
        order = []
        if len(self.processes.keys()) > 0:
            memoryUsage = {}
            for name, stream in self.processes.items():
                memoryUsage[name] = stream.sum_of_files()
            memorySorted = sorted(memoryUsage.items(), key=operator.itemgetter(1)) # sort by size
            for i in range(len(memorySorted)-1, -1, -1):
                order.append(memorySorted[i][0])
        return order

    def find_storage(self, usbMountDirForm='/media/usb', maxFileDeletions=10): # TODO: look into putting in space needed as an argument instead
        # if we are using usb storage, try to move to a new drive if possible
        storageFull = True
        if dvrutils.storage_is_usb(self.storagePath, usbMountDirForm):
            self.mainLogger.info("Scanning for free USB storage space...")
            storagePath = dvrutils.find_usb_storage(minBytesFree=self.spaceNeeded, corruptedUSBs=self.corruptedUSBs)
            print('Found path {}'.format(storagePath))

            if storagePath is not None:     # if there was something to switch to, do that
                if (storagePath != self.storagePath) and (self.storagePath != usbMountDirForm):
                    self.mainLogger.info("Found available storage device at {}".format(storagePath))
                    self.storagePath = storagePath
                    self.mainLogger.info("Switching to new storage device...".format(storagePath))
                    storageFull = False
                    self.restart_logger()
                    self.mainLogger.info("***** STREAMRECORDER STORAGE PATH CHANGED *****")
                    self.mainLogger.info("Logging at level {}".format(self.logLevel))

        # if we can overwrite old files, tell each stream to delete files until there is enough space
        elif self.overwriteFiles:
            nFilesDeleted = 0
            streamNum = 0
            for _ in range(maxFileDeletions):
                storageFull = self.check_available_storage(spaceNeeded=self.spaceNeeded)
                if not storageFull:
                    break
                largestStreams = self.get_stream_size_order()
                # delete_oldest_file returns the filename if it deleted one, otherwise, None
                if self.processes[largestStreams[streamNum]].delete_oldest_file(minDaysOld=self.minDaysOld) is not None:
                    nFilesDeleted += 1
                else:
                    self.mainLogger.warning("Stream {} did not delete a file when requested to!".format(largestStreams[streamNum]))
                    if streamNum < len(largestStreams)-1:
                        streamNum += 1
                    else:
                        break
            if storageFull:
                self.mainLogger.critical("There is still no space. Tried to delete files from {} stream(s), and deleted {} file(s).".format(streamNum+1, nFilesDeleted))
       # otherwise if (for whatever reason) we can't move to new storage and we can't delete files, log that we're full and wait
        if storageFull and not self.storageFull:
            self.mainLogger.critical("All available storage space is full! All recording processes will be suspended until this is fixed!")
            self.storageFull = storageFull

    def check_stream(self, name, stream):
        if stream.should_record():
            # if it should be, make sure it is alive
            self.mainLogger.debug("Stream {} is in the active period!".format(name))
            if not stream.isActive:
                stream.logger.info("Stream has entered active period!")
                stream.isActive = True
            if not stream.thread_isAlive():
                # if it died, restart it
                self.mainLogger.info("Restarting stream thread {}".format(name))
                location = os.path.join(self.storagePath, name)
                if not os.path.exists(location):
                    self.mainLogger.info("Folder {} does not exist. Creating it now!".format(location))
                    os.makedirs(location)
                stream.start_recording(location)
                self.streamStarts[name] = time.time()
            else:
                # wait initTime before checking file growth
                if name in self.streamStarts:
                    if (time.time() - self.streamStarts[name]) < self.initTime:
                        self.mainLogger.info("Waiting to check stream {} ...".format(name))
                        return
                self.mainLogger.debug("Checking file growth on stream {}".format(name))
                # if it's still alive, make sure the file is still growing
                isGrowing = stream.check_file_growth()          # kills the process if the file stops growing
                self.mainLogger.debug("File from stream {} is {} at {}/s".format(name, 'growing' if isGrowing else 'not growing', dvrutils.format_size(stream.fileGrowthRate)))

        else:   # don't restart if we are outside the active time
            self.mainLogger.debug("Stream {} is outside the active period!".format(name))
            if stream.isActive:
                stream.logger.info("Stream has left the active period! Recording will resume when directed to by the schedule.")
                stream.isActive = False

    # checks if all scheduled streams have failed some number of consecutive times,
    # if they have, add the current storage drive to the corrupted drives list
    def check_fail_count(self, usbMountDirForm='/media/usb', changeDirAtFailCount=3):
        if len(self.processes) > 0:
            failCount = 0
            scheduledCount = 0
            for name, stream in self.processes.items():
                failCount += 1 if stream.consecutiveFailCount >= changeDirAtFailCount and stream.should_record() else 0
                scheduledCount += 1 if stream.should_record() else 0
            if failCount == scheduledCount and failCount > 0:
                if usbMountDirForm in os.path.abspath(self.storagePath):
                    self.mainLogger.warning('Adding the path {} to the corrupted usb list!'.format(os.path.abspath(self.storagePath)))
                    self.corruptedUSBs.append(os.path.abspath(self.storagePath))
                    self.spaceNeeded = -1
                    self.find_storage(usbMountDirForm, 0)
                for name, stream in self.processes.items():
                    stream.consecutiveFailCount = 0

    def check_stream_threads(self, usbMountDirForm='/media/usb', maxFileDeletions=10, changeDirAtFailCount=3):
        # check available storage space
        storageFull = self.check_available_storage()
        self.mainLogger.debug("Storage is {} with {} free and {} needed".format("full" if storageFull else "not full", self.strBytesFree, self.strSpaceNeeded))

        # if we don't have enough space, do something about it
        if storageFull:
            self.mainLogger.info("Insufficient storage space. Need {} to record but only {} is available!".format(dvrutils.format_size(self.spaceNeeded), dvrutils.format_size(self.bytesFree)))
            self.find_storage(usbMountDirForm, maxFileDeletions)
        elif self.storageFull:
            self.storageFull = False
            self.mainLogger.critical("Storage is available again! Starting recording threads...")

        if not self.storageFull:        # don't bother checking anything if storage is full, since we know the threads will (eventually) fail continuously
            # watch threads to restart when they return (if we are in the active period and there is available storage space)
            for name, stream in self.processes.items():
                self.mainLogger.debug("Checking stream {}".format(name))
                self.check_stream(name, stream)
            self.check_fail_count(usbMountDirForm, changeDirAtFailCount)
        time.sleep(5)

    #------------------------------------------------------------
    # End Stream Managing Functions
    #============================================================

class ProcessManager(object):
    def __init__(self, dvrName, streamName, storagePath, container, recordingSchedule, createFilename=False,
                 logLocation='../logs', logLevel='INFO', initTime=15, endAtDuration=False):
        self.dvrName = dvrName
        self.streamName = streamName
        self.storagePath = os.path.abspath(storagePath)
        self.container = container
        self.recordingSchedule = recordingSchedule
        self.logLocation = logLocation
        self.logLevel = logLevel
        self.logger = dvrutils.setup_logging(os.path.join(logLocation,streamName+'.log'),
                            logLevel, "{}.{}".format(dvrName, streamName), logToFile=True, logToStdout=False)
        self.initTime = initTime
        self.endAtDuration = endAtDuration
        self.createFilename = createFilename
        self.recordingName = "{0}_{1}".format(self.dvrName, self.streamName)
        self.processLogName = os.path.join(self.logLocation, 'process_{}_{}.log'.format(self.streamName, time.strftime('%Y%m%d')))
        self.avgFileSize = 0
        self.thread = None
        self.currentFile = None
        self.lastFile = None
        self.isActive = self.should_record()
        self.killAtErrorCount = 6
        self.checkInterval = 15
        self.lastSize = 0
        self.fileSize = []
        self.noGrowthCount = 0
        self.fileGrowthRate = 0
        self.isRecording = False
        self.timeSinceStart = 0
        self.startTime = None
        self.process = None
        self.lastThreadStart = 0
        self.timeSinceThreadStart = 0
        self.consecutiveFailCount = 0

    def start_recording(self, path=''):
        if path != '':
            self.storagePath = path
        self.thread = threading.Thread(target=self.record)
        self.thread.daemon = True
        self.thread.start()
        self.lastThreadStart = time.time()
        self.logger.debug("Thread for stream {} started!".format(self.streamName))

    def thread_isAlive(self):
        self.timeSinceThreadStart = time.time() - self.lastThreadStart
        if self.timeSinceThreadStart < self.initTime:
            # give process a chance to warm up before we let anyone know it's real status
            self.logger.info("Stream {} is still warming up...".format(self.streamName))
            return True
        else:
            return self.isRecording

    def delete_oldest_file(self, minDaysOld=1):
        self.logger.info('Stream was instructed to delete the oldest file. Finding oldest file...')
        fileDeleted = None
        # get all the files recorded by this stream
        files = glob.glob("{}*".format(os.path.join(self.storagePath, self.recordingName)))
        # go through the files and get the modification times for each file
        mtimes = {f: os.path.getmtime(f) for f in files}
        # delete the file with the oldest (min) modification time
        self.logger.info("Found {} files eligible for deletion!".format(len(mtimes)))
        if len(mtimes) > 0:
            minTime = min(mtimes.values())  # get the min time
            oldestFile = [k for k, v in mtimes.items() if v == minTime][0]  # find the filename

            # check the age of the file and refuse to delete it if it is more than minDaysOld time
            daysOld = time.localtime().tm_yday - time.localtime(minTime).tm_yday
            self.logger.info("Oldest file is {}, last modified at {} ({} days ago)".format(oldestFile, time.strftime('%Y%m%d-%H%M%S', time.localtime(minTime)), daysOld))
            if daysOld >= minDaysOld:
                self.logger.info("DELETING file now!")
                try:
                    os.remove(oldestFile)
                    fileDeleted = oldestFile
                    self.logger.info("File deleted successfully!")
                except:
                    self.logger.warning("Could not delete file! Something is wrong...")
            else:
                self.logger.warning("This file is too new to be deleted! Files created within the past {} days will not be deleted under any circumstances!".format(minDaysOld))
        return fileDeleted

    def sum_of_files(self):
        try: # in case file get deleted while summing
            return sum([os.path.getsize(f) for f in glob.glob("{}*".format(os.path.join(self.storagePath, self.recordingName)))])
        except:
            self.logger.warning('Something happened while summing files')
            return 0

    def get_avg_file_size(self, safetyFactor=1.0):
        fileCount = len(glob.glob("{}*".format(os.path.join(self.storagePath, self.recordingName))))
        if fileCount > 0:
            self.avgFileSize = safetyFactor*(self.sum_of_files()/fileCount)  # calculate average, multiply by a safety factor
        else:
            self.avgFileSize = 0
        return self.avgFileSize

    def should_record(self): # NOTE: overloaded in CameraRecorder
        return self.recordingSchedule.check_recording_schedule()

    def check_file_growth(self):
        self.logger.debug("Performing file growth check on stream {}...".format(self.streamName))
        if self.startTime is None: # if it hasn't started, it can't be growing
            self.logger.info("Start time is {}! The process has not been started!".format(self.startTime))
            self.reset()
            return False
        if self.currentFile is None: # if there is no file just return True
            self.logger.debug('Skipping growth check because file is unknown!')
            return True
        self.timeSinceStart = time.time() - self.startTime
        self.logger.debug("Process was started {} seconds ago".format(self.timeSinceStart))
        if self.timeSinceStart < self.initTime: # wait until ffmpeg is initialized
            self.logger.debug("Skipping growth check until process has {} seconds to warm up".format(self.initTime))
            return True
        if self.process is not None:
            pstat = self.process.poll()
            if not os.path.exists(self.currentFile):
                self.logger.debug("File {} does not exist!".format(self.currentFile))
                # if the file doesn't exist by now, something must be wrong
                pstat = self.process.poll()
                if pstat is None:
                    self.logger.error("The file has not been created {} seconds past start! Killing process now to (hopefully) restart correctly!".format(round(self.timeSinceStart)))
                    dvrutils.kill_process(self.process, self.logger)
                    self.reset()                                    # restart the stream status so a new recording starts
                    return False
                else:
                    self.logger.error("Process crashed without creating a file! The command string passed may be incorrect! Printing it below...")
                    self.logger.error(self.cmd_args)
                    return False
            else:
                # if it does (which it should) check the file size
                self.currSize = os.path.getsize(self.currentFile)
                self.logger.debug("File {} is currently {}".format(self.currentFile, dvrutils.format_size(self.currSize)))
                if len(self.fileSize) == 0:
                    self.fileGrowthRate = self.currSize
                else:
                    self.lastSize = self.fileSize[-1]
                    self.fileGrowthRate = (self.currSize-self.lastSize)/float(self.checkInterval)
                    # zero our error counter if the file grows again
                    if self.fileGrowthRate == 0:
                        self.noGrowthCount += 1
                    else:
                        self.noGrowthCount = 0
                    if self.noGrowthCount >= self.killAtErrorCount:

                        self.logger.error("The file being recorded has not grown for {} seconds (after {} checks). Killing process to restart now!".format(self.noGrowthCount*self.checkInterval,self.noGrowthCount))
                        dvrutils.kill_process(self.process, self.logger)
                        self.reset()
                        return False

                # add this size to the list and increment the index
                self.logger.debug("File {} is currently {}, growing at {}/s".format(self.currentFile, dvrutils.format_size(self.currSize), dvrutils.format_size(self.fileGrowthRate)))
                self.fileSize.append(self.currSize)
                return (self.fileGrowthRate != 0)           # return if the fileGrowthRate is not 0 (growing, True) or 0 (not growing, false)
        else:
            self.logger.debug("Process for stream {} is None!".format(self.streamName))
            return True

    def reset(self):
        self.logger.info("Resetting stream status parameters for new recording...")
        if self.process and self.process.poll() is None:
            self.logger.warning("Process was still running. Killing it now...")
            dvrutils.kill_process(self.process, self.logger)
        self.lastSize = 0
        self.fileSize = []
        self.noGrowthCount = 0
        self.fileGrowthRate = 0
        self.logger.debug("Stream reset complete!")

    def build_command(self):
        raise NotImplementedError('build_command() is not overridden')

    def initialize_recording(self, duration):
        self.startTime = time.time()
        self.cmd_args = self.build_command(duration)
        self.logger.debug('The command arguments are the following {}'.format(self.cmd_args))
        self.logger.info("Starting recording stream {} for {} seconds.".format(self.streamName, duration))
        with open(self.processLogName, 'a') as f:
            f.write('### PROCESS LOG FOR PROCESS {} ###\n\n'.format(self.currentFile if self.createFilename else 'Unknown'))
        try:
            # all ouptut should go to stderr, but watch stdout too anyways
            self.process = subprocess.Popen(self.cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, universal_newlines=True)
        except Exception as f:
            raise f
        self.timeSinceStart = 0
        self.logger.debug("Recording for stream {} started! Sleeping for {} seconds before performing a process check...".format(self.streamName, self.initTime))
        time.sleep(self.initTime)
        self.logger.debug("Checking process status on stream {}".format(self.streamName))
        self.timeSinceStart = time.time() - self.startTime
        pstat = self.process.poll()
        self.logger.debug("Process on stream {} is {} {} seconds after start".format(self.streamName, 'active' if pstat is None else 'INactive', self.timeSinceStart))
        self.stopTime = self.startTime + duration if self.endAtDuration else self.startTime + duration + 60
        return pstat

    def rename_file(self, dateStr, startTimeStr):
        endTimeStr = time.strftime("%H%M%S")
        newFname = self.format_file_name(dateStr, startTimeStr, endTimeStr, unique=False)
        if newFname != self.currentFile:
            self.lastFile = dvrutils.get_unique_filename(newFname)
            self.logger.info("Renaming file {} to {} to reflect true end time...".format(self.currentFile,self.lastFile))
            try:
                os.rename(self.currentFile, self.lastFile)
            except Exception as e:
                self.logger.error(e)
                self.logger.error("Could not rename file {}! This is probably not good...".format(self.currentFile))
                self.lastFile = self.currentFile
        else:
            self.lastFile = self.currentFile
        self.currentFile = self.lastFile

    def stop_recording(self):
        pstat = self.process.poll()
        if pstat is None:
            if self.endAtDuration:
                self.logger.info('Process is at stop point, killing it now.')
            else:
                self.logger.warning("Process was caught running well past the point it should have stopped! Killing it now!")
            dvrutils.kill_process(self.process, self.logger)
            self.reset()
        with open(self.processLogName, 'a') as f:
            f.write('### END PROCESS LOG FOR PROCESS {} ###\n\n'.format(self.currentFile if self.createFilename else 'Unknown'))
    
    def get_recording_duration(self):
        """Get the amount of time to record given the current time."""
        return self.recordingSchedule.get_recording_duration()
    
    def record(self):
        # reset the recording parameters
        self.logger.debug("Entered record...")
        self.reset()
        self.cmd_args = []
        self.logger.debug("Checking recording schedule...")

        if self.should_record():
            self.logger.debug("Stream {} should record now!".format(self.streamName))
            self.isRecording = True
            self.startTime = time.time()
            # calculate recording time
            duration = self.get_recording_duration()
            self.logger.debug("Stream will record for {} seconds!".format(duration))

            if self.createFilename:
                self.logger.debug("Getting date/time info...")
                dateStr, startTimeStr, endTimeStr = \
                    time.strftime("%Y%m%d"), time.strftime("%H%M%S"), time.strftime("%H%M%S",time.localtime(time.time()+duration))

                self.logger.debug("Formatting file name...")
                self.currentFile = self.format_file_name(dateStr, startTimeStr, endTimeStr)
            else:
                self.createFilename = None

            pstat = self.initialize_recording(duration)
            self.logger.debug("Entering process check loop on stream {} until planned stop time ~{}".format(self.streamName, time.strftime("%H:%M:%S", time.localtime(self.stopTime))))
            while pstat is None:
                self.logger.debug("Waiting {} seconds until next check...".format(self.checkInterval))
                time.sleep(self.checkInterval)
                self.log_process_output()
                self.timeSinceStart = time.time() - self.startTime
                self.logger.debug("Checking process timeliness...")
                if time.time() > self.stopTime:
                    self.stop_recording()
                pstat = self.process.poll()

            if pstat == 0:
                self.logger.info("Recording {} completed at {}!".format(self.streamName, time.strftime("%H:%M:%S")))
                self.consecutiveFailCount = 0
            else:
                self.logger.error("Recording {} exited at {} with returncode {}!".format(self.streamName, time.strftime("%H:%M:%S"), pstat))
                self.consecutiveFailCount += 1
            if self.currentFile is not None:
                self.rename_file(dateStr, startTimeStr)

            # sync the disk(s) to make sure everything is written to storage
            self.logger.info("Recording file {} ended!".format(self.streamName))
            self.logger.debug("Syncing disk buffers...")
            subprocess.call(['sync'])
            self.isRecording = False
            self.logger.debug("Exiting camera_record...")
            return self.lastFile if self.createFilename else False

    def format_file_name(self, dateStr, startTimeStr, endTimeStr, unique=True):
        fileName = "{rn}-{ds}_{st}-{et}.{vc}".format(rn=self.recordingName,
                                                     ds=dateStr,
                                                     st=startTimeStr,
                                                     et=endTimeStr,
                                                     vc=self.container)
        fileName = os.path.join(self.storagePath,fileName)
        if unique:
            fileName = dvrutils.get_unique_filename(fileName)
        return fileName

    def log_process_output(self): # NOTE: overloaded in CameraRecorder
        pass # Was not implemented for CommandRecorder becuase of issues with stalling

class CameraRecorder(ProcessManager):

    def __init__(self, dvrName, streamName, streamURL, videoContainer, codec, quality, framerate,
                 recordingSchedule, videoLocation, ffmpegLogLevel='warning', ffmpegLogFileForm='ffmpeg.log',
                 logLocation='../logs/', logLevel='INFO', initTime=15, endAtDuration=False,
                 performRestarts=False, user=None, passwd=None, manufacturer=None, ipAddr=None, port=None,
                 onvifDir=None, streamType=None):
        self.lastReboot = time.strftime('%Y%m%d') # These need to be set before super is called, so should_record can get called in PM ctor
        self.isRestarting = False
        self.continueRecordingPast = 0
        super(CameraRecorder, self).__init__(dvrName, streamName, videoLocation,
             videoContainer, recordingSchedule, True, logLocation, logLevel, initTime, endAtDuration)
        self.streamURL = streamURL
        self.codec = codec
        self.quality = quality
        self.framerate = framerate
        self.recordingSchedule = recordingSchedule
        self.ffmpegLogFileForm = ffmpegLogFileForm
        self.ffmpegLogLevel = ffmpegLogLevel
        self.initTime = initTime
        self.performRestarts = performRestarts
        self.user = user
        self.passwd = passwd
        self.manufacturer = manufacturer
        self.ip = ipAddr
        self.port = port
        self.onvifDir = onvifDir
        self.streamType = streamType
        if self.manufacturer != None and self.manufacturer.lower() != 'axis' and self.performRestarts:
            self.set_camera_time()
        self.getStreamType()
    
    def getStreamType(self):
        """Get the stream type, i.e. RTSP, HLS, DASH, or MJPEG. Result is
        saved in the streamType attribute.
        """
        if self.streamType is not None:
            self.logger.debug("Forcing streaming protocol: '{}' ...".format(
                self.streamType))
        else:
            url = self.streamURL.lower()
            if url.startswith('rtsp://'):
                self.streamType = 'RTSP'
            elif url.startswith('http://'):
                # NOTE this is probably OK for HLS/DASH/MJPEG differentiation,
                # though there may be better approaches...
                if url.endswith('.m3u8') or url.endswith('.m3u'):
                    self.streamType = 'HLS'
                elif url.endswith('.mpd'):
                    self.streamType = 'DASH'
                else:
                    # if HTTP and no other information, assume (and force) MJPEG
                    self.streamType = 'MJPEG'
            self.logger.debug("Streaming protocol: '{}' ...".format(
                self.streamType))
        
        # up the killAtErrorCount if we're recording HLS or DASH - we need to
        # allow for longer periods of 0 growth since it sends little clips
        # TODO this may not be sufficient if clips are really long (should be
        # pretty rare in our applications, but who knows...)
        if self.isHlsDash():
            self.killAtErrorCount = 20
            self.logger.debug("Upping killAtErrorCount to {} ...".format(
                self.killAtErrorCount))
    
    def isHlsDash(self):
        """Return if the stream is HLS/DASH."""
        return self.streamType in ['HLS', 'DASH']
    
    def get_recording_duration(self):
        """Get the amount of time to record given the current time. Runs some
        additional checks on HLS/DASH recordings to try and prevent small
        clips at the ends of recording intervals.
        """
        # get the "standard" duration
        dur = self.recordingSchedule.get_recording_duration()
        
        # if HLS/DASH, check if the clip will be too short (defined as less
        # than 60 seconds, as long as clips are not 1-minute clips)
        if self.isHlsDash() and dur < 60 and self.recordingSchedule.fileDurationMinutes != 1:
            self.logger.info("Clip duration {} too short! Merging with next clip!".format(dur))
            extraDur = dur + 1
            atTime = time.time() + extraDur
            dur2 = self.recordingSchedule.get_recording_duration(atTime=atTime)
            return dur2 + extraDur
        return dur
    
    def build_command(self, videoDuration):
        self.logger.debug("Building ffmpeg command string...")
        cmd_args = []
        if self.streamType == 'RTSP':
            cmd_args = ['ffmpeg', '-y', '-use_wallclock_as_timestamps', '1', '-loglevel', self.ffmpegLogLevel,
                             '-rtsp_transport', 'tcp', '-stimeout', '5000000', '-i', self.streamURL, '-c:v', self.codec,
                             '-r', str(self.framerate), '-t', str(videoDuration), self.currentFile]
        elif self.isHlsDash():
            # NOTE that we don't set a framerate for HLS/DASH
            cmd_args = ['ffmpeg', '-y', '-loglevel', self.ffmpegLogLevel, '-i', self.streamURL,
                        '-c', self.codec, '-t', str(videoDuration), self.currentFile]
        elif self.streamType == 'MJPEG':
            cmd_args = ['ffmpeg', '-y', '-use_wallclock_as_timestamps', '1', '-loglevel', self.ffmpegLogLevel,
                             '-f', 'mjpeg', '-i', self.streamURL, '-c:v', self.codec, '-qscale:v', str(self.quality),
                             '-r', str(self.framerate), '-t', str(videoDuration), self.currentFile]
        return cmd_args

    def log_process_output(self):
        self.logger.debug('Outputing to process log')
        with open(self.processLogName, 'a') as logFile:
            for oLine in self.process.stdout:
                eptime = time.time()
                ms = int(1000*(eptime-math.floor(eptime)))
                logFile.write(time.strftime("%H:%M:%S,{} -- ".format(ms))+oLine)
        self.logger.debug('Output to process log finished')

    def set_camera_time(self, camera=None):
        try:
            if camera is None:
                from onvif import ONVIFCamera # onvif path appended in StreamManager ctor
                logging.getLogger().handlers.pop()
                camera = ONVIFCamera(self.ip, self.port, self.user, self.passwd, os.path.join(self.onvifDir, 'wsdl'))
            time_params = camera.devicemgmt.create_type('SetSystemDateAndTime')
            time_params.DateTimeType = 'Manual'
            time_params.DaylightSavings = pytz.timezone("CST6CDT").localize(datetime.datetime.utcnow(), is_dst=None).tzinfo._dst.seconds != 0
            time_params.TimeZone = "CST6CDT"
            rightNow = datetime.datetime.utcnow()
            time_params['UTCDateTime'] = {
                'Date': {
                    'Year': rightNow.year,
                    'Month': rightNow.month,
                    'Day': rightNow.day
                },
                'Time': {
                    'Hour': rightNow.hour,
                    'Minute': rightNow.minute,
                    'Second': rightNow.second
                }
            }

            camera.devicemgmt.SetSystemDateAndTime(time_params)
            self.logger.info('Camera Time set to {}'.format(time_params))
        except:
            self.logger.warning('Seting time on camera {} failed'.format(self.streamName))

    def camera_restart(self, stopAtCount=3):
        self.isRestarting = True
        if self.manufacturer.lower() != 'axis':
            self.onvif_restart(stopAtCount)
        else:
            self.fts_restart(stopAtCount)
        self.isRestarting = False
        self.continueRecordingPast = time.time() + 60

    def onvif_restart(self, stopAtCount=3):
        self.logger.info('Restarting onvif camera...')
        tries = 0
        completed = False
        while not completed and tries < stopAtCount:
            tries += 1
            try:
                from onvif import ONVIFCamera # onvif path appended in StreamManager ctor
                if logging.getLogger().handlers:
                    logging.getLogger().handlers.pop()
                camera = ONVIFCamera(self.ip, self.port, self.user, self.passwd, os.path.join(self.onvifDir, 'wsdl'))
                status = camera.devicemgmt.SystemReboot()
                self.logger.info('Restart for camera {}, complete with status {}'.format(self.streamName, status))
                completed = True
                self.set_camera_time(camera)
            except Exception as e:
                self.logger.warning('Reboot failed on try {}/{}, printing out error message...'.format(tries, stopAtCount))
                time.sleep(60)

    def fts_restart(self, stopAtCount=3):
        self.logger.info('Restarting fts camera...')
        tries = 0
        status = 0
        while status != 200 and tries < stopAtCount:
            tries += 1
            try:
                r = requests.get('http://{}:{}@{}/axis-cgi/admin/restart.cgi'.format(self.user, self.passwd, self.ip))
                status = r.status_code
            except:
                status = 0
            if status == 200:
                self.logger.info('Reboot sucessful with status 200')
            elif status == 401:
                from requests.auth import HTTPDigestAuth
                r = requests.get('http://{}/axis-cgi/admin/restart.cgi'.format(self.ip),auth=HTTPDigestAuth(self.user,self.passwd))
                status = r.status_code
                self.logger.info('Rebooted using HTTPDigestAuth')
            else:
                self.logger.warning('Reboot failed on try {}/{} with status {}'.format(tries, stopAtCount, status))
                time.sleep(60)

    def should_record(self):
        self.logger.debug('Checking if camera should restart...')
        # if the camera hasn't been restarted yet today, restart it
        if self.lastReboot != time.strftime('%Y%m%d'):
            self.lastReboot = time.strftime('%Y%m%d')
            self.camera_restart()
        if self.isRestarting or time.time() < self.continueRecordingPast:
            return False
        return self.recordingSchedule.check_recording_schedule()

class CommandRecorder(ProcessManager):

    def __init__(self, dvrName, streamName, storagePath, container, commandStr, recordingSchedule,
                 logLocation = '../logs/', logLevel='INFO', initTime=15):
        self.commandStr = commandStr
        braces = re.compile(r'{.*}')
        keyWords = [w.strip('{ }').lower() for w in braces.findall(self.commandStr)]
        createFilename = True if 'filename' in keyWords else False
        super(CommandRecorder, self).__init__(dvrName, streamName, storagePath, container,
             recordingSchedule, createFilename, logLocation, logLevel, 15, True)


    def build_command(self, duration=None):
        if self.createFilename:
            return self.commandStr.format(filename=self.currentFile).split()
        return self.commandStr.split()
