import os
import sys
import math
import time
import traceback
import logging, logging.handlers
import subprocess

def grabframe(streamUrl, outputImage, loglevel='quiet'):
    """
    Download a single frame from the stream at streamUrl into the file 
    outputImage. Returns the return code of the ffmpeg commmand.
    """
    return subprocess.call(['ffmpeg','-loglevel',loglevel,'-y','-rtsp_transport','tcp','-i',streamUrl,'-vframes','1','-q','1',outputImage])

def yesno(prompt,default='n'):
    yn = input(prompt).strip().lower()
    yn = yn if len(yn) > 0 else default.lower()
    if yn == 'y':
        return True
    else:
        return False

def format_time(tsecs, withSeconds=True):
    try:
        DH = float(tsecs)/3600
        HH = int(math.floor(DH))
        DM = (DH-HH)*60
        MM = int(math.floor(DM))
        tStr = "{:0>2d}:{:0>2d}".format(HH,MM)
        if withSeconds:
            SS = int(math.floor((DM-MM)*60))
            tStr += ":{:0>2d}".format(SS)
        return tStr
    except:
        return None

def format_size(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def longest_common_substring(s1, s2):
    m = [[0] * (1 + len(s2)) for i in range(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest: x_longest]

def print_recording_params(logger, vidParams, streamName):
    logger.info("{} recording parameters:".format(streamName))
    logger.info("   Container: {}".format(vidParams[streamName]['container']))
    logger.info("   Codec: {}".format(vidParams[streamName]['codec']))
    logger.info("   FrameRate: {}".format(vidParams[streamName]['framerate']))
    logger.info("   Quality: {}".format(vidParams[streamName]['quality']))
    logger.info("   FileDuration: {} minutes".format(vidParams[streamName]['filedurationminutes']))
    logger.info("   Schedule: {}".format(vidParams[streamName]['schedule']))

def read_storage_size_value(s):
    '''Read a string defining an amount of data storage, expressed as a percentage, decimal, or human-readable size'''
    if '%' in s:
        return float()/100
    # TODO

def setup_logging(logFilePath, logLevelStr, deviceName, logger=None, logFormat='%(asctime)s - %(name)s - %(levelname)s - %(message)s', logToFile=True, logToStdout=True, logToEmail=False, emailLogLevelStr='CRITICAL', mailhost=('smtp.gmail.com',587), fromaddr='gordbot720@gmail.com', toaddrs=None, subject=None, credentials=('gordbot720@gmail.com','b0rgd0+!'), secure=tuple()):
    try:
        loglevel = int(logLevelStr)
    except ValueError:
        loglevel = logLevelStr.upper()
    ploglevel = logging.getLevelName(loglevel)
    
    # get the root logger if they didn't give us one
    if logger is None:
        logger = logging.getLogger(deviceName)
    
    # replace all handlers so we can start over (NOTE: a for loop over the loggers doesn't always work...)
    start = time.time()
    while len(logger.handlers) > 0:
        logger.removeHandler(logger.handlers[0])
        if (time.time() - start) > 30:              # in the odd event we get stuck in this loop, time out after 30 seconds to avoid blocking the main program
            print ("Logging handlers could not be removed! I don't know why...")
            break
    
    # set the format and log level
    formatter = logging.Formatter(logFormat)
    logger.setLevel(ploglevel)
    
    # file handler for log file
    if not logToFile and not logToStdout:
        logToFile = True        # assume they want a file if they said nothing
    
    if logToFile:
        fh = logging.FileHandler(logFilePath)
        fh.setLevel(ploglevel)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    # stream handler for debugging
    if logToStdout:
        ch = logging.StreamHandler()
        ch.setLevel(ploglevel)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    
    # print log level for the user
    logger.info("setup_logging - Logging at level {}".format(loglevel))
    
    if logToEmail:
        if toaddrs is not None:
            try:
                # make sure we give the handler a list of recipients if the user only gave us one address as a string (not in a list)
                if isinstance(toaddrs, str):
                    toaddrs = [toaddrs]
                
                # create the handler
                subject = "Log message from {}".format(deviceName) if subject is None else subject
                sh = logging.handlers.SMTPHandler(mailhost, fromaddr, toaddrs, subject, credentials=credentials, secure=secure)
                
                # set the log level
                try:
                    emailLogLevel = int(emailLogLevelStr)
                except ValueError:
                    emailLogLevel = emailLogLevelStr.upper()
                pEmailLogLevel = logging.getLevelName(emailLogLevel)
                sh.setLevel(pEmailLogLevel)
                sh.setFormatter(formatter)
                logger.addHandler(sh)
                logger.info("setup_logging - Log messages of level {} and worse will be sent via email from {} to {}".format(emailLogLevel, fromaddr, toaddrs))
            except:
                logger.error("An error was encountered while setting up email logging! Email logging will be unavailable until this is fixed!")
        else:
            logger.warning("Cannot perform email logging without any recipients!")
    
    return logger

def restart_program(execPath):
    time.sleep(1)                               # sleep for 1 sec
    os.execv(execPath, sys.argv)                # replaces current process with new one with same args

def log_fatal_error(appDir, embeddedLogDirectory='crashlogs', msg=''):
    '''Logs fatal errors that prevent logging to external storage'''
    if msg == '':
        msg = traceback.format_exc()
    embeddedLogDirectory = os.path.join(appDir, embeddedLogDirectory)
    if not os.path.exists(embeddedLogDirectory):
        os.makedirs(embeddedLogDirectory)
    print(msg)
    with open(os.path.join(embeddedLogDirectory, time.strftime("crashlog-%m%d%y.log")), 'a') as dumpFile:
        dumpFile.write(time.strftime('##---- Crash at %H:%M:%S ----##\n'))
        dumpFile.write(msg)
        dumpFile.write('\n##---- End crash report ----##\n\n')

'''Reads boolean value from string, considering true, 1, yes, and y as True, everything else False'''
def str_to_bool(string):
    return string.lower() in ['true', '1', 'yes', 'y']

'''Checks if a path conforms to usbmount configuration (and is therefore a USB storage device)'''
def storage_is_usb(storagePath, usbMountDirForm='/media/usb'):
    if len(storagePath) >= len(usbMountDirForm):
        if storagePath[0:len(usbMountDirForm)] == usbMountDirForm:
            return True
    return False

'''Finds a USB device that is mounted with at least minMBFree (megabytes) remaining, kills the program otherwise'''
def find_usb_storage(embeddedLogDirectory='crashlogs', basePath='/media/usb', firstDrive=0, minBytesFree=1000000000, corruptedUSBs=[]):
    # look at the usb directories to check if they are mounted and if they are full
    driveNum = firstDrive
    usbPath = basePath + str(driveNum)
    availableDirs = []
    while os.path.exists(usbPath):
        # directory exists, check if it is a mountpoint
        if os.path.ismount(usbPath) and (os.path.abspath(usbPath) not in corruptedUSBs):
            # check the available storage space
            bytesFree = get_disk_usage(usbPath, mounted=True)
            if bytesFree > minBytesFree:
                availableDirs.append(usbPath)
        driveNum += 1
        usbPath = basePath + str(driveNum)      # gives us /media/usb0, /media/usb1,...
    newPath = None
    if availableDirs != []:
        smallestDir = (availableDirs[0], os.statvfs(availableDirs[0]).f_bavail)
        for i in range(1, len(availableDirs)):
            dirSize = os.statvfs(availableDirs[i]).f_bavail
            if dirSize < smallestDir[1]:
                smallestDir = (availableDirs[i], dirSize)
        newPath = smallestDir[0]
    return newPath  

def get_disk_usage(path, mounted=True):
    bytesFree = -1
    if os.path.exists(path):
        if (os.path.ismount(path) and mounted) or (not mounted):            # if this is a mountpoint or they don't care, return the size
            s = os.statvfs(path)
            bytesFree = (s.f_bavail * s.f_frsize)
    return bytesFree                                                        # otherwise return -1 to reflect an error

def get_unique_filename(fname, nZeros=5):
    # Returns a unique filename made from fname (appends suffix 00000-99999 if file exists to avoid overwriting)
    newname = fname
    if os.path.exists(fname):
        i = 0
        basename, ext = os.path.splitext(fname)
        while os.path.exists(newname):
            fnumStr = ('%0{}d'.format(nZeros) % i,)[0]
            newname = basename + '_' + fnumStr + ext
            i += 1
    return newname
    
def kill_process(process, logger):
    pstat = process.poll()
    if pstat is None:
        try:
            process.terminate()
            time.sleep(3)
        except:
            logger.error('Process did not respond to SIGINT')
    elif pstat is not None:
        logger.error("Process killed successfully!")
    pstat = process.poll()
    if pstat is None:
        logger.error("Process is still alive! Trying SIGKILL!")
        try:
            process.kill()
            time.sleep(3)
        except:
            logger.error("Process did not respond to SIGKILL!")
    pstat = process.poll()
    if pstat is None:
        logger.critical("Could not kill process! Somthing weird is happening!")
        