#!/usr/bin/python3
import time
import datetime
import os
import re
import subprocess
import psutil
import threading

from configobj import ConfigObj


def mean(elements):
    if len(elements) == 0:
        return 0
    return sum(elements) / len(elements)

# Returns a test schedule where the test schedule
# The test schedule starts at the current time, and records for two minutes, then stops for two minutes,
# then continues again for two minutes
#
# Output Arguments:
# - The test schedule string 
def get_schedule():
    schedule_str = time.strftime('%H%M') + '-' + datetime.datetime.fromtimestamp( time.time() + 120).strftime('%H%M') + ';'
    schedule_str += datetime.datetime.fromtimestamp( time.time() + 240).strftime('%H%M') + '-' + datetime.datetime.fromtimestamp( time.time() + 360).strftime('%H%M')
    return schedule_str

# Returns the file path that should be used based on the string given.
#
# Input Arguments:
# - path: the path of the file being checked
#
# Output Arguments:
# - The path that will be used
def get_file_path(path): # TODO: ask about this
    if path == '/media/usb':
        return '/media/usb0/'
    else:
        if path[-1] != '/':
            return path + '/'
        else:
            return path

# Reads in an input string of stream params and what they should default to if they aren't in the string
#
# Input arguments:
# input_vars: A string of the variables, Form (VarName1=Value1;VarName2=Value2)
# default_vars: A complete dictionary of all the default variables. If it is not in the dictionary, it will
# not be added, even if it is in the input_vars
#
# Output Arguments:
# - A dictionary of the variables
def get_vars(input_vars, default_vars):
    input_vars.strip()
    if input_vars[0] == '(':
        input_vars = input_vars[1:-1]
    str_params = input_vars.split(';')
    given_vars = {}
    for p in str_params:
        key, value = p.split('=')
        key.strip()
        value.strip()
        given_vars[key.lower()] = value
        
    return_vars = {}
    for var in default_vars:
        if var.lower() in given_vars:
            return_vars[var.lower()] = given_vars[var.lower()]
        else:
            return_vars[var.lower()] = default_vars[var]
    return return_vars
    
# Takes in the test configuation object, and creates the stream configuration files for the streamrecorder program
#
# Input arguments:
# - testConfig - a configObj containing the test params
#
# testConfig params:
# - length: the length of the test (in seconds)
# - checkInterval: how often to check the file sizes (in seconds)
# - FrameRate: the default frame rate
# - fileDurationMinutes: the default recording length (in minutes)
# - Schedule: the schedule string, if 'test', a test schedule will be created
#
# - Storage['path']: the file path to record files in
# - Storage['minDaysOld']: Minimum days old files should be to delete them
# - Storage['Mounted']: True/False
# - Storage['OverwrieFiles']: True/False, whether or not to overwrite files
#
# - Streams['stream name']: ip, Manufatorer, stream type, schedule (optional), overriden parameters (optional)
#
# Output Actions:
# - Create the configuration files
#
# Output Arguments: a list of the stream information to check later [name, schedule, file path, stream variables, command/None]
def create_cfg_files(testConfig):
    files = file_list()
    testParams = read_cfg_file(testConfig)
    streamrecorderConfig = ConfigObj()
    streamrecorderConfig.filename = files[0]
    streamrecorderConfig['LogLevel'] = 'error'
    streamrecorderConfig['ffmpegLogLevel'] = 'error'
    streamrecorderConfig['Port'] = testParams['port']
    streamrecorderConfig['StreamConfig'] = 'tests/testStreams.cfg'
    streamrecorderConfig['CamConfig'] = 'camerainfo.cfg'
    streamrecorderConfig['performrestarts'] = 'True'
    streamrecorderConfig['onvifdir'] = testParams['onvifdir']
    streamrecorderConfig['Storage'] = testParams['storage']
    streamrecorderConfig['sender'] = testParams['sender']
    streamrecorderConfig.write()        
    
    file_path = get_file_path(testParams['storage']['path'])

    streamsConfig = ConfigObj()
    streamsConfig.filename = files[1]
    streamsConfig['container'] = testParams['container'] if 'container' in testParams else 'avi'
    streamsConfig['framerate'] = testParams['framerate'] if 'framerate' in testParams else '15'
    streamsConfig['filedurationminutes'] = testParams['filedurationminutes'] if 'filedurationminutes' in testParams else '60'
    streamsConfig['codec'] = testParams['codec'] if 'codec' in testParams else 'copy'
    streamsConfig['quality'] = testParams['quality'] if 'quality' in testParams else '7'
    streamsConfig['streams'] = testParams['streams'] if 'streams' in testParams else None
    
    if 'schedule' in testParams:
        defaultSchedule = get_schedule() if testParams['schedule'].lower() == 'test' else testParams['schedule']
    else:
        defaultSchedule = 'always'
    streamsConfig['Schedule'] = defaultSchedule
    
    for key, value in streamsConfig.items():
        streamsConfig.pop(key, None)
        streamsConfig[key.lower()] = value
        
    default_vars = {'framerate' : streamsConfig['framerate'], 
                    'filedurationminutes' : streamsConfig['filedurationminutes'], 
                    'codec' : streamsConfig['codec'], 
                    'quality' : streamsConfig['quality']}         
    streams = []
    for streamName, values in testParams['streams'].items():
        ipRe = re.compile(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')
        extraParams = len(values) - 1 if type(values) == list else 0
        elementOne = values[0] if type(values) == list else values
        valueOffset = 2 if ipRe.match(elementOne) else 0
        if extraParams - valueOffset == 0:
            streams.append([streamName, defaultSchedule, os.path.join(file_path, streamName), default_vars, None])
        elif extraParams - valueOffset == 1:
            streams.append([streamName, values[1+valueOffset], os.path.join(file_path, streamName), default_vars, None])
            streamsConfig['streams'][streamName][1+valueOffset] = get_schedule() if values[1+valueOffset].lower() == 'test' else values[1+valueOffset]
        elif extraParams - valueOffset == 2:
            streams.append([streamName, values[1+valueOffset], os.path.join(file_path, streamName), get_vars(values[2+valueOffset], default_vars), None])
            streamsConfig['streams'][streamName][1+valueOffset] = get_schedule() if values[1+valueOffset].lower() == 'test' else values[1+valueOffset]
        if 'http://' not in elementOne.split()[0] and 'rtsp://' not in elementOne.split()[0] and (not ipRe.match(elementOne)):
            streams[-1][4] = elementOne
    streamsConfig.write()
    return streams

def read_cfg_file(testConfig):
    testDict = {}
    for key, value in testConfig.items():
        if type(value) is dict:
            subDict = {}
            for k, v in value:
                subDict[k.lower()] = v
            testDict[key.lower()] = subDict
        else:
            testDict[key.lower()] = value
    return testDict

# Calculated the expected number of files
# It gives a range in case the start and end times are near the start of a new interval
#
# Params:
# start - the start time
# end - the end time
# inteval - the length of each file
# schedule_str - the string that represents the schedule, if not 'test' assumes the stream was constantly recording
#
# Output:
# - The range of the expect files
#
# NOTE: this function only works with the schedule string 'test', if it is not 'test', it assmunes that the streams were being recorded non-stop between the start and end times     
def expected_files_created(start, end, interval, schedule_str):
    if schedule_str == 'test':
        if end - start < 120:
            duration_minutes = (end - start) / 60.0
            files = duration_minutes // interval + 1
            files += 1 if ((start / 60.0) % interval) + (duration_minutes % interval) > interval+0.001 else 0 # +0.001 to deal with lack of precision with doubles
        else:
            duration_minutes = (120 - (start % 60)) / 60.0
            files = duration_minutes // interval + 1
            files += 1 if ((start / 60.0) % interval) + (duration_minutes % interval) > interval+0.001 else 0
        if end - start + (start % 60) > 240:
            new_start = ((start + 240) // 60) * 60
            new_end = min(new_start + 120, end)
            duration_minutes = (new_end - new_start) / 60.0
            files += duration_minutes // interval + 1
            files += 1 if (new_start / 60.0) % interval + (duration_minutes % interval) > interval+0.001 else 0
    else:
        duration_minutes = (end - start) / 60.0
        files = duration_minutes // interval + 1
        files += 1 if ((start / 60.0) % interval) + (duration_minutes % interval) > interval+0.001 else 0
    min_files, max_files = files, files
    
    if start % (interval * 60) > (interval * 60) - 15:
        min_files -= 1
    if end % (interval * 60) < 35:
        min_files -= 1
    
    return (min_files, max_files)

# Looks at the command put in to start ffmpeg, and read the arguments
#
# Output Argumets:
# - a dictionary where the keys are the stream name and the values are a list of each part of the command
def check_command():
    time.sleep(3) # make sure streams have actually started
    if time.time() % 60 < 20 or time.time() % 60 > 5: # make sure to not catch cameras at a break
        time.sleep(25)
    pidstr = subprocess.check_output(['pidof', 'ffmpeg'])
    pids = pidstr.split()
    cmds = [psutil.Process(int(pid)).cmdline() for pid in pids]
    stream_cmds = {}
    for cmd in cmds:
        stream = ''.join(''.join(cmd[-1].split('_')[1:-1]).split('-')[0:-1]) # find stream name in stream filename
        stream_cmds[stream] = cmd
    return stream_cmds

def run_streamrecorder():
    process = subprocess.Popen(['python', '../streamrecorder.py', '-c', file_list()[0], '-l', 'debug'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    thread = threading.Thread(target=empty_log_output, args=(process,))
    thread.daemon = True
    thread.start()
    return process, thread
  
def empty_log_output(process):
    while True:
        for i in process.stdout:
            pass
        time.sleep(10)

def file_list():
    srDir = os.path.abspath(os.path.dirname(__file__))
    testSRFile = os.path.join(srDir, 'testStreamrecorder.cfg')
    testStreamFile = os.path.join(srDir, 'testStreams.cfg')
    return (testSRFile, testStreamFile)

def get_disk_usage(path, mounted=True):
    bytesFree = -1
    if os.path.exists(path):
        if (os.path.ismount(path) and mounted) or (not mounted):            # if this is a mountpoint or they don't care, return the size
            s = os.statvfs(path)
            bytesFree = (s.f_bavail * s.f_frsize)
    return bytesFree

def rewrite_dvrutils(size):   
    new_max_size = get_disk_usage('/mnt/video') - size
    with open('../streamrecorder/dvrutils.py', 'a') as f:
        add_str = \
        '''\n\ndef get_disk_usage(path, mounted=True):
        bytesFree = -1
        if os.path.exists(path):
            if (os.path.ismount(path) and mounted) or (not mounted):            # if this is a mountpoint or they don't care, return the size
                s = os.statvfs(path)
                bytesFree = (s.f_bavail * s.f_frsize)
        return bytesFree - {}'''.format(new_max_size if new_max_size > 0 else 0)
        f.write(add_str)