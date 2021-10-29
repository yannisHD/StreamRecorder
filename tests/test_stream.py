import builtins
import os
import pytest
import shutil
import sys
import time
import subprocess
from configobj import ConfigObj
from unittest import mock

sys.path.append('..')

from streamrecorder import stream
from streamrecorder import dvrutils

def get_schedule_mock(schedStr='', durationMinutes=60):
    def new_check_schedule():
        if schedStr == 'always':
            return True
        return False
    schedMock = mock.Mock()
    schedMock.schedStr = schedStr
    schedMock.durationMinutes = durationMinutes
    schedMock.check_recording_schedule.side_effect = new_check_schedule
    schedMock.get_recording_duration.return_value = 90
    return schedMock

@mock.patch(__name__ + '.' + 'dvrutils.setup_logging')
def make_camera_recorder(logMock):
    logMock.return_value = mock.Mock()
    return stream.CameraRecorder('dvrName', 'Axis', 'MJPEG',
                              'avi', 'copy', 7, 15, get_schedule_mock('always', 1), 'storage', logLevel='debug')

@mock.patch(__name__ + '.' + 'dvrutils.setup_logging')
def make_command_recorder(logMock):
    logMock.return_value = mock.Mock()
    return stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'python writefile.py -f {filename}',
                                  get_schedule_mock('always', 1))

@pytest.fixture(params=['CameraRecorder', 'CommandRecorder'], scope='function')
def all_classes(request):
    if request.param == 'CameraRecorder':
        yield make_camera_recorder()
    elif request.param == 'CommandRecorder':
        yield make_command_recorder()
# =============================================================================
# Tests for just CameraRecorder
# =============================================================================

def test_camerarecorder_ctor():
    if not os.path.exists('../logs'):
        os.mkdir('../logs')
    open('../logs/Axis.log', 'w')
    recorder = stream.CameraRecorder('dvrName', 'Axis', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                              'avi', 'copy', 7, 15, get_schedule_mock('always', 1), 'storage')
    assert recorder.dvrName == 'dvrName'
    assert recorder.streamName == 'Axis'
    assert recorder.streamURL == 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi'
    assert recorder.container == 'avi'
    assert recorder.codec == 'copy'
    assert recorder.quality == 7
    assert recorder.framerate == 15
    assert recorder.storagePath == os.path.abspath('storage')
    assert recorder.logLocation == '../logs/'
    assert recorder.ffmpegLogLevel == 'warning'
    assert recorder.processLogName == '../logs/process_Axis_{}.log'.format(time.strftime('%Y%m%d'))
    assert recorder.recordingName == 'dvrName_Axis'
    assert recorder.avgFileSize == 0
    assert recorder.thread == None
    assert recorder.isActive == True
    assert recorder.killAtErrorCount == 6
    assert recorder.checkInterval == 15
    assert recorder.initTime == 15
    assert recorder.lastSize == 0
    assert recorder.fileSize == []
    assert recorder.noGrowthCount == 0
    assert recorder.fileGrowthRate == 0
    assert recorder.isRecording == False
    assert recorder.timeSinceStart == 0
    assert recorder.startTime == None
    assert recorder.process == None
    assert recorder.lastThreadStart == 0
    assert recorder.timeSinceThreadStart == 0
    assert recorder.endAtDuration == False
    assert recorder.performRestarts == False
    assert recorder.user == None
    assert recorder.passwd == None
    assert recorder.manufacturer == None
    assert recorder.ip == None
    assert recorder.port == None
    recorder2 = stream.CameraRecorder('dvrName', 'Axis', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                              'avi', 'copy', 7, 15, get_schedule_mock('always', 1), 'storage', 'error', 'video.log',
                              '../logs/', 'debug', 20, True, True, 'user', 'pass', 'manu', '10.179.1.252', 80)
    assert recorder2.ffmpegLogLevel == 'error'
    assert recorder2.ffmpegLogFileForm == 'video.log'
    assert recorder2.logLocation == '../logs/'
    assert recorder2.logLevel == 'debug'
    assert recorder2.initTime == 20
    assert recorder2.endAtDuration == True
    assert recorder2.user == 'user'
    assert recorder2.passwd == 'pass'
    assert recorder2.manufacturer == 'manu'
    assert recorder2.ip == '10.179.1.252'
    # Just make sure this can be constructed
    recorder3 = stream.CameraRecorder('dvrName', 'Axis', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                              'avi', 'copy', 7, 15, get_schedule_mock('always', 1), 'storage', ffmpegLogLevel='warning',
                              ffmpegLogFileForm='ffmpeg.log', logLocation='../logs/', logLevel='INFO', initTime=15, endAtDuration=False,
                              performRestarts=False, ipAddr=None, port=80, user='user', passwd='pass', manufacturer='manu')

def test_camerarecorder_build_command():
    recorder = stream.CameraRecorder('dvrName', 'Axis', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                              'avi', 'copy', 7, 15, get_schedule_mock('always', 1), 'storage', logLevel='debug')
    recorder.currentFile = 'dir/file.avi'
    cmd = recorder.build_command(300)
    assert cmd == ['ffmpeg', '-y', '-use_wallclock_as_timestamps', '1', '-loglevel',
                                 'warning', '-f', 'mjpeg', '-i',
                                 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                                 '-c:v', 'copy', '-qscale:v', '7', '-r', '15', '-t', '300', 'dir/file.avi']
    recorder.streamURL = 'rtsp://user:pass@ipaddr/stream'
    cmd = recorder.build_command(500)
    assert cmd == ['ffmpeg', '-y', '-use_wallclock_as_timestamps', '1', '-loglevel',
                                 'warning', '-rtsp_transport', 'tcp', '-stimeout', '5000000',
                                 '-i', 'rtsp://user:pass@ipaddr/stream', '-c:v', 'copy', '-r',
                                 '15', '-t', '500', 'dir/file.avi']

def test_camerarecorder_should_record():
    recorder = make_camera_recorder()
    recorder.isRestarting = True
    assert recorder.should_record() == False
    recorder.isRestarting = False
    recorder.continueRecordingPast = time.time() + 15
    assert recorder.should_record() == False
    recorder.continueRecordingPast = time.time() - 1
    assert recorder.should_record() == True
    recorder.recordingSchedule = get_schedule_mock('')
    assert recorder.should_record() == False

@mock.patch('onvif.ONVIFCamera')
def test_set_camera_time(camInitMock):
    class TimeDict:
        def __init__(self):
            self.myDict = {}
        def __setitem__(self, x, y):
            self.myDict[x] = y
        def __getitem__(self, item):
            return self.myDict[item]
    camMock = mock.Mock()
    camInitMock.return_value = camMock
    timeDict = TimeDict()
    camMock.devicemgmt.create_type.return_value = timeDict
    recorder = make_camera_recorder()
    recorder.set_camera_time(camMock)
    camMock.devicemgmt.SetSystemDateAndTime.assert_called_once()
    assert timeDict.DateTimeType == 'Manual'
    assert timeDict.DaylightSavings == True
    camMock2 = mock.Mock()
    timeDict2 = TimeDict()
    camMock.devicemgmt.create_type.return_value = timeDict2
    recorder.set_camera_time(camMock2)
    camMock.devicemgmt.SetSystemDateAndTime.assert_called_once()
    assert timeDict.DateTimeType == 'Manual'
    assert timeDict.DaylightSavings == True

@mock.patch('time.sleep')
@mock.patch('requests.get')
def test_fts_camera_restart(getMock, sleepMock):
    requestMock = mock.Mock()
    requestMock.status_code = 200
    getMock.return_value = requestMock
    recorder = make_camera_recorder()
    recorder.user = 'username'
    recorder.passwd = 'passwd'
    recorder.ip = '242.0.0.0'
    recorder.fts_restart()
    getMock.assert_called_with('http://username:passwd@242.0.0.0/axis-cgi/admin/restart.cgi')
    getMock.return_value = 0
    recorder.fts_restart(1)

@mock.patch.object(stream.CameraRecorder, 'set_camera_time')
@mock.patch('onvif.ONVIFCamera')
def test_onvif_camera_restart(camInitMock, setTimeMock):
    camMock = mock.Mock()
    camInitMock.return_value = camMock
    recorder = make_camera_recorder()
    recorder.user = 'username'
    recorder.passwd = 'passwd'
    recorder.ip = '242.0.0.0'
    recorder.port = '80'
    recorder.onvifDir = '/path/to/onvif'
    recorder.onvif_restart()
    camInitMock.assert_called_once_with('242.0.0.0', '80', 'username', 'passwd', '/path/to/onvif/wsdl')
    camMock.devicemgmt.SystemReboot.assert_called_once()
    setTimeMock.assert_called_once()


# =============================================================================
# Tests for just CommandRecorder
# =============================================================================

def test_commandrecorder_ctor(): # TODO: check that all varients of 'filename' work
    recorder = stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'python -f {filename} writefile.py',
                                      get_schedule_mock('always', 1), logLocation='../logs/', logLevel='INFO',
                                      initTime=15)
    assert recorder.dvrName == 'dvrName'
    assert recorder.streamName == 'command'
    assert recorder.storagePath == os.path.abspath('storage')
    assert recorder.container == 'txt'
    assert recorder.recordingSchedule.schedStr == 'always'
    assert recorder.logLocation == '../logs/'
    assert recorder.logLevel == 'INFO'
    assert recorder.initTime == 15
    assert recorder.endAtDuration == True
    assert recorder.createFilename == True
    assert recorder.commandStr == 'python -f {filename} writefile.py'
    recorder2 = stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'sleep 10', get_schedule_mock('always', 1),
                                       '../logs', 'error', 20)
    assert recorder2.createFilename == False
    assert recorder2.logLocation == '../logs'
    assert recorder2.logLevel == 'error'
    assert recorder2.initTime == 15
    # just make sure the this can be constructed
    recorder3 = stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'python -f {filename} writefile.py',
                                      get_schedule_mock('always', 1), logLocation='../logs/', logLevel='INFO',
                                      initTime=15)

def test_commandrecorder_build_command():
    recorder = stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'python ../tests/writefile.py -f {filename}',
                                      get_schedule_mock('always', 1))
    recorder.currentFile = 'dir/file.txt'
    assert recorder.build_command() == ['python', '../tests/writefile.py', '-f', 'dir/file.txt']
    assert recorder.build_command(50) == ['python', '../tests/writefile.py', '-f', 'dir/file.txt']

def test_commandrecorder_should_record():
    recorder = stream.CommandRecorder('dvrName', 'command', 'storage', 'txt', 'python writefile.py -f {filename}',
                                      get_schedule_mock('always', 1))
    assert recorder.should_record() == True
    recorder.recordingSchedule = get_schedule_mock('')
    assert recorder.should_record() == False

# =============================================================================
# Tests for both classes
# =============================================================================

@mock.patch('threading.Thread')
def test_start_recording(threadMock, all_classes):
    recorder = all_classes
    recorder.storagePath = '/path/to/video'
    tMock = mock.Mock()
    threadMock.return_value = tMock
    recorder.start_recording()
    assert recorder.storagePath == '/path/to/video'
    assert tMock.daemon == True
    threadMock.assert_called_once_with(target=recorder.record)
    tMock.start.assert_called_once()

    recorder2 = all_classes
    recorder2.start_recording('newLocation')
    assert recorder2.storagePath == 'newLocation'

@mock.patch('time.time')
def test_thread_isAlive(timeMock, all_classes):
    timeMock.return_value = 300
    recorder = all_classes
    assert recorder.thread_isAlive() == False
    recorder.lastThreadStart = 300
    assert recorder.thread_isAlive() == True
    recorder.isRecording = True
    recorder.lastThreadStart = 270
    assert recorder.thread_isAlive() == True
    recorder.isRecording = False
    assert recorder.thread_isAlive() == False

@mock.patch('time.strftime')
@mock.patch('os.remove')
@mock.patch('time.localtime')
@mock.patch('os.path.getmtime')
@mock.patch('glob.glob')
def test_delete_oldest_file(globMock, getmtimeMock, localMock, removeMock,
                            strftimeMock, all_classes):

    def new_localtime(minTime=None):
        returnValue = mock.Mock()
        if minTime == None:
            returnValue.tm_yday = 5
        else:
            returnValue.tm_yday = minTime
        return returnValue

    recorder = all_classes
    globMock.return_value = []
    assert recorder.delete_oldest_file() == None

    localMock.side_effect = new_localtime
    globMock.return_value = ['file1.txt', 'file2.txt', 'file3.txt']
    getmtimeMock.side_effect = [5, 4, 5, 5, 4, 5]
    assert recorder.delete_oldest_file() == 'file2.txt'
    removeMock.assert_called_with('file2.txt')

@mock.patch('glob.glob')
@mock.patch('os.path.getsize')
def test_sum_of_files(sizeMock, globMock, all_classes):
    recorder = all_classes
    recorder.storagePath = '/storage/path'
    recorder.recordingName = 'rname'
    globMock.return_value = []
    assert recorder.sum_of_files() == 0
    globMock.return_value = ['file1.txt', 'file2.txt']
    sizeMock.side_effect = [1, 4]
    assert recorder.sum_of_files() == 5
    globMock.assert_called_with('/storage/path/rname*')

@mock.patch('glob.glob')
@mock.patch.object(stream.ProcessManager, 'sum_of_files')
def test_get_avg_file_size(sumMock, globMock, all_classes):
    recorder = all_classes
    globMock.return_value == 0
    recorder.avgFileSize = 1
    assert recorder.get_avg_file_size() == 0
    assert recorder.avgFileSize == 0
    globMock.return_value = ['file1.txt', 'file2.txt']
    sumMock.return_value = 80
    assert recorder.get_avg_file_size() == 40

@mock.patch('os.path.getsize')
@mock.patch('os.path.exists')
@mock.patch(__name__ + '.' + 'dvrutils.format_size')
@mock.patch(__name__ + '.' + 'dvrutils.kill_process')
@mock.patch.object(stream.ProcessManager, 'reset')
def test_check_file_growth(resetMock, killMock, formatMock, existsMock, sizeMock, all_classes):
    processMock = mock.Mock()
    recorder = all_classes
    recorder.cmd_args = []
    assert recorder.check_file_growth() == False # no start time

    resetMock.assert_called_once()
    recorder.startTime = time.time()
    assert recorder.check_file_growth() == True # no currentFile

    recorder.currentFile = '/not/real/file'
    recorder.startTime = time.time() - 10
    assert recorder.check_file_growth() == True # ffmpeg initializing

    recorder.startTime = time.time() - 20
    recorder.process = None
    assert recorder.check_file_growth() == True # process does not exists

    recorder.process = processMock
    processMock.poll.return_value = None
    existsMock.return_value = False
    assert recorder.check_file_growth() == False # process if running, but didn't create file
    killMock.assert_called_once()

    resetMock.reset_mock()
    killMock.reset_mock()
    processMock.poll.return_value = 1
    assert recorder.check_file_growth() == False # process ended without a file
    killMock.assert_not_called()
    resetMock.assert_not_called()

    existsMock.return_value = True
    sizeMock.return_value = 0
    recorder.fileSize = []
    assert recorder.check_file_growth() == False # file was just created, but isn't growing

    recorder.fileSize = []
    sizeMock.return_value = 1
    assert recorder.check_file_growth() == True # file was just create, and is growing

    recorder.killAtErrorCount = 3
    recorder.noGrowthCount = 1
    assert recorder.check_file_growth() == False # file is not growing, but it's not time to kill the process
    killMock.assert_not_called()

    recorder.killAtErrorCount = 3
    recorder.noGrowthCount = 2
    assert recorder.check_file_growth() == False # file is not growing, and it's time to kill the process
    killMock.assert_called_once()

@mock.patch(__name__ + '.' + 'dvrutils.kill_process')
def test_reset(killProcessMock, all_classes):
    recorder = all_classes
    processMock = mock.Mock()
    processMock.poll.return_value = 0
    recorder.process = processMock
    recorder.lastSize = 1
    recorder.fileSize = [0,0,0]
    recorder.noGrowthCount = 10
    recorder.fileGrowthRate = 10
    recorder.reset()
    assert recorder.lastSize == 0
    assert recorder.fileSize == []
    assert recorder.noGrowthCount == 0
    assert recorder.fileGrowthRate == 0
    killProcessMock.assert_not_called()
    processMock.poll.return_value = None
    recorder.reset()
    killProcessMock.assert_called_once()

@mock.patch.object(stream.CommandRecorder, 'build_command')
@mock.patch.object(stream.CameraRecorder, 'build_command')
@mock.patch('subprocess.Popen')
@mock.patch('time.sleep')
@mock.patch('time.time')
def test_initialize_recording(timeMock, sleepMock, popenMock, camBuildMock,
                              cmdBuildMock, all_classes):
    recorder = all_classes
    timeMock.side_effect = [300, 315, 300, 315]
    processMock = mock.Mock()
    processMock.poll.return_value = 'poll return'
    popenMock.return_value = processMock
    camBuildMock.return_value = 'cmd_args'
    cmdBuildMock.return_value = 'cmd_args'
    if os.path.isfile(recorder.processLogName):
        os.remove(recorder.processLogName)
    recorder.currentFile = 'dir/file.avi' # supposed to get initialized before
    recorder.endAtDuration = True
    assert recorder.initialize_recording(90) == 'poll return'
    assert recorder.startTime == 300
    assert recorder.timeSinceStart == 15
    sleepMock.assert_called_once_with(15)
    popenMock.assert_called_once_with('cmd_args', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, universal_newlines=True)
    assert recorder.stopTime == 390
    assert os.path.isfile(recorder.processLogName)

    recorder.endAtDuration = False
    recorder.initialize_recording(90)
    assert recorder.stopTime == 450

@mock.patch('os.rename')
@mock.patch('time.strftime')
@mock.patch(__name__ + '.' + 'dvrutils.get_unique_filename')
@mock.patch.object(stream.ProcessManager, 'format_file_name')
def test_rename_file(formatMock, uniqueMock, strfMock, renameMock, all_classes):
    recorder = all_classes
    formatMock.return_value = 'formattedName'
    uniqueMock.return_value = 'uniqueName'
    strfMock.return_value = '080000'
    startFile = 'dvrName_Axis-20180101_010001-020000.avi'
    recorder.currentFile = startFile
    recorder.rename_file('20180801', '010001')
    formatMock.assert_called_with('20180801', '010001', '080000', unique=False)
    uniqueMock.assert_called_with('formattedName')
    renameMock.assert_called_with(startFile, 'uniqueName')

@mock.patch.object(stream.ProcessManager, 'reset')
@mock.patch(__name__ + '.' + 'dvrutils.kill_process')
def test_stop_recording(killMock, resetMock, all_classes):
    with mock.patch('builtins.open', mock.mock_open()) as m:
        recorder = all_classes
        processMock = mock.Mock()
        processMock.poll.return_value = 0
        logMock = mock.Mock()
        recorder.logger = logMock
        recorder.process = processMock
        recorder.endAtDuration = True
        recorder.processLogName = '/log/file/path.log'
        recorder.stop_recording()
        m.assert_called_with('/log/file/path.log', 'a')
        killMock.assert_not_called()
        resetMock.assert_not_called()

        processMock.poll.return_value = None
        recorder.stop_recording()
        killMock.assert_called_once()
        resetMock.assert_called_once()
        logMock.info.assert_called()
        logMock.warning.assert_not_called()

@mock.patch('time.time')
@mock.patch('subprocess.call')
@mock.patch.object(stream.ProcessManager, 'rename_file')
@mock.patch.object(stream.ProcessManager, 'stop_recording')
@mock.patch.object(stream.ProcessManager, 'initialize_recording')
@mock.patch.object(stream.ProcessManager, 'format_file_name')
@mock.patch.object(stream.CommandRecorder, 'should_record')
@mock.patch.object(stream.CameraRecorder, 'should_record')
@mock.patch.object(stream.ProcessManager, 'reset')
def test_record(resetMock, camRecordMock, cmdRecordMock, formatMock, initMock,
                stopMock, renameMock, callMock, timeMock, all_classes):
    recorder = all_classes
    timeMock.return_value = 300
    camRecordMock.return_value = False
    cmdRecordMock.return_value = False
    assert recorder.record() == None
    resetMock.assert_called_once()
    resetMock.reset_mock()
    camRecordMock.return_value = True
    cmdRecordMock.return_value = True
    formatMock.return_value = os.path.abspath('storage/file.txt')
    processMock = mock.Mock()
    processMock.poll = None
    initMock.return_value = processMock
    recorder.stopTime = 299
    recorder.createFilename = False
    assert recorder.record() == False
    assert recorder.isRecording == False
    callMock.assert_called_once_with(['sync'])
    renameMock.assert_not_called()
    resetMock.assert_called_once()
    recorder.createFilename = True
    recorder.lastFile = 'file.txt'
    assert recorder.record() == 'file.txt'
    renameMock.assert_called_once() # TODO: add params

@mock.patch(__name__ + '.' + 'dvrutils.get_unique_filename')
def test_format_file_name(uniqueMock, all_classes):
    recorder = all_classes
    uniqueMock.return_value = 'uniqueName'
    expected_filename = os.path.abspath('storage/dvrName_{}-20180101_000000-010000.{}'.format(recorder.streamName, recorder.container))
    assert recorder.format_file_name('20180101', '000000', '010000', False) == expected_filename
    expected_filename = os.path.abspath('storage/dvrName_{}-20180101_000000-010000_00000.{}'.format(recorder.streamName, recorder.container))
    assert recorder.format_file_name('20180101', '000000', '010000', True) == 'uniqueName'

#==============================================================================
# Stream Manager Tests
#==============================================================================

@pytest.fixture
def stream_manager():
    if os.path.exists('storage'):
        shutil.rmtree('storage')
    os.mkdir('storage')
    yield stream.StreamManager('dvrName', 'execPath', 'storage', mock.Mock(), 'logs', overwriteFiles=True, minDaysOld=0, port=80)
    shutil.rmtree('storage')

def test_ctor():
    manager = stream.StreamManager('dvrName', 'execPath', 'storage', None, 'logs')
    assert manager.dvrName == 'dvrName'
    assert manager.execPath == 'execPath'
    assert manager.storagePath == 'storage'
    assert manager.logLocation == '../logs/'
    assert manager.logLevel == 'INFO'
    assert manager.logFilePath == 'logs'
    assert manager.overwriteFiles == False
    assert manager.minDaysOld == 3
    assert manager.initTime == 15
    assert manager.performRestarts == False
    assert 'dir/onvifDir' not in sys.path
    assert manager.port == None
    assert manager.mainLogger == None
    assert manager.storageFull == False
    manager = stream.StreamManager('dvrName', 'execPath', 'storage', None, 'logs', 'debug',
                                   'dir/logs', True, 4, 20, True, 'dir/onvifDir', 80)
    assert manager.logLevel == 'debug'
    assert manager.logLocation == 'dir/logs'
    assert manager.overwriteFiles == True
    assert manager.minDaysOld == 4
    assert manager.initTime == 20
    assert manager.performRestarts == True
    assert manager.port == 80
    assert 'dir/onvifDir' in sys.path

@mock.patch('os.makedirs')
@mock.patch('os.path.exists')
def test_add_video_stream(existsMock, makeMock, stream_manager):
    manager = stream_manager
    existsMock.return_value = True
    manager.add_video_stream('stream0', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                             'avi', 'copy', 6, 10, get_schedule_mock('always'))
    makeMock.assert_not_called()
    assert 'stream0' in manager.processes
    assert manager.processes['stream0'].dvrName == 'dvrName'
    assert manager.processes['stream0'].streamName == 'stream0'
    assert manager.processes['stream0'].streamURL == 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi'
    assert manager.processes['stream0'].container == 'avi'
    assert manager.processes['stream0'].quality == 6
    assert manager.processes['stream0'].framerate == 10
    assert manager.processes['stream0'].recordingSchedule.schedStr == 'always'
    assert manager.processes['stream0'].storagePath == os.path.abspath('storage/stream0')
    assert manager.processes['stream0'].ffmpegLogLevel == 'warning'
    assert manager.processes['stream0'].ffmpegLogFileForm == 'ffmpeg.log'
    assert manager.processes['stream0'].logLocation == '../logs/'
    assert manager.processes['stream0'].logLevel == 'INFO'
    assert manager.processes['stream0'].initTime == 15
    assert manager.processes['stream0'].endAtDuration == False
    assert manager.processes['stream0'].user == None
    assert manager.processes['stream0'].passwd == None
    assert manager.processes['stream0'].manufacturer == None
    assert manager.processes['stream0'].ip == None
    assert manager.processes['stream0'].port == 80
    manager = stream_manager
    existsMock.return_value = False
    manager.storagePath = '/path/to/dir'
    manager.add_video_stream('stream0', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                             'avi', 'copy', 6, 10, get_schedule_mock('always'), 'info', 'user', 'pass', 'manu', '10.179.1.252')
    makeMock.assert_called_with('/path/to/dir/stream0')
    assert manager.processes['stream0'].ffmpegLogLevel == 'info'
    assert manager.processes['stream0'].user == 'user'
    assert manager.processes['stream0'].passwd == 'pass'
    assert manager.processes['stream0'].manufacturer == 'manu'

@mock.patch('os.makedirs')
@mock.patch('os.path.exists')
def test_add_command_stream(existsMock, makeMock, stream_manager):
    manager = stream_manager
    existsMock.return_value = True
    manager.add_command_stream('stream0', 'txt', 'sleep 10', get_schedule_mock('always'))
    makeMock.assert_not_called()
    assert 'stream0' in manager.processes
    assert manager.processes['stream0'].dvrName == 'dvrName'
    assert manager.processes['stream0'].streamName == 'stream0'
    assert manager.processes['stream0'].storagePath == os.path.abspath('storage/stream0')
    assert manager.processes['stream0'].container == 'txt'
    assert manager.processes['stream0'].commandStr == 'sleep 10'
    assert manager.processes['stream0'].recordingSchedule.schedStr == 'always'
    assert manager.processes['stream0'].logLocation == '../logs/'
    assert manager.processes['stream0'].logLevel == 'INFO'
    assert manager.processes['stream0'].initTime == 15
    manager.storagePath = '/path/to/dir'
    existsMock.return_value = False
    manager.add_command_stream('stream0', 'txt', 'sleep 10', get_schedule_mock('always'))
    makeMock.assert_called_with('/path/to/dir/stream0')

def test_start_streams(stream_manager):
    manager = stream_manager
    camMock0 = mock.Mock()
    camMock1 = mock.Mock()
    manager.processes = {'stream0' : camMock0, 'stream1' : camMock1}
    manager.start_streams()
    camMock0.start_recording.assert_called_once()
    camMock1.start_recording.assert_called_once()

@mock.patch(__name__ + '.' + 'dvrutils.setup_logging')
def test_restart_logger(setupMock, stream_manager):
    manager = stream_manager
    manager.logLevel = 'INFO'
    manager.logFilePath = 'log/path.log'
    manager.dvrName = 'newDvrName'
    manager.restart_logger()
    setupMock.assert_called_with('log/path.log', 'INFO', 'newDvrName', logToFile=True,
                                 logToStdout=True, logToEmail=False, toaddrs=None)

@mock.patch(__name__ + '.' + 'dvrutils.get_disk_usage')
@mock.patch(__name__ + '.' + 'dvrutils.format_size')
def test_check_available_storage(formatMock, diskMock, stream_manager):
    manager = stream_manager
    diskMock.return_value = 200
    formatMock.side_effect = [None, 'spaceNeeded', 'bytesNeeded',
                              None, None, 'spaceNeeded', 'bytesNeeded']
    assert manager.check_available_storage(100) == False
    camMock = mock.Mock()
    camMock.get_avg_file_size.return_value = 150
    manager.processes = {'stream0' : camMock, 'stream1' : camMock}
    assert manager.check_available_storage() == True

def test_get_stream_size_order(stream_manager):
    manager = stream_manager
    assert manager.get_stream_size_order() == []
    smallCam = mock.Mock()
    smallCam.sum_of_files.return_value = 50
    mediumCam = mock.Mock()
    mediumCam.sum_of_files.return_value = 100
    largeCam = mock.Mock()
    largeCam.sum_of_files.return_value = 200
    manager.processes = {'small' : smallCam, 'large' : largeCam, 'medium' : mediumCam}
    assert manager.get_stream_size_order() == ['large', 'medium', 'small']

@mock.patch.object(stream.StreamManager, 'get_stream_size_order')
@mock.patch.object(stream.StreamManager, 'check_available_storage')
@mock.patch.object(stream.StreamManager, 'restart_logger')
@mock.patch(__name__ + '.' + 'dvrutils.find_usb_storage')
@mock.patch(__name__ + '.' + 'dvrutils.storage_is_usb')
def test_find_storage(isUsbMock, findMock, restartMock, availableMock,
                      orderMock, stream_manager):
    manager = stream_manager
    isUsbMock.return_value = True
    findMock.return_value = '/new/path'
    manager.spaceNeeded = 100
    manager.find_storage()
    assert manager.storageFull == False
    restartMock.assert_called_once()
    restartMock.reset_mock()
    isUsbMock.return_value = False
    availableMock.side_effect = [True, True, True, False]
    orderMock.return_value = ['large', 'medium', 'small']
    manager.overwriteFiles = True
    largeMock = mock.Mock()
    mediumMock = mock.Mock()
    smallMock = mock.Mock()
    largeMock.delete_oldest_file.side_effect = ['file.txt', None]
    mediumMock.return_value = 'file.txt'
    manager.processes = {'large' : largeMock, 'medium' : mediumMock, 'small' : smallMock}
    manager.find_storage()
    assert largeMock.delete_oldest_file.call_count == 2
    assert mediumMock.delete_oldest_file.call_count == 1
    assert smallMock.delete_oldest_file.call_count == 0
    assert manager.storageFull == False
    manager.overwriteFiles = False
    manager.find_storage()
    assert manager.storageFull == True

@mock.patch('time.time')
@mock.patch('os.path.join')
@mock.patch('os.makedirs')
@mock.patch('os.path.exists')
@mock.patch(__name__ + '.' + 'dvrutils.format_size')
def test_check_stream(formatMock, existsMock, makeMock, joinMock,
                      timeMock, stream_manager):
    manager = stream_manager
    streamMock = mock.Mock()
    streamMock.isActive = False
    streamMock.thread_isAlive.return_value = False
    streamMock.should_record.return_value = True
    existsMock.return_value = False
    joinMock.return_value = '/path/to/dir'
    timeMock.return_value = 300
    manager.check_stream('stream0', streamMock)
    assert streamMock.isActive == True
    makeMock.assert_called_with('/path/to/dir')
    streamMock.start_recording.assert_called_once()
    assert 'stream0' in manager.streamStarts
    streamMock.thread_isAlive.return_value = True
    manager.streamStarts['stream0'] = 299
    manager.initTime = 15
    manager.check_stream('stream0', streamMock)
    streamMock.check_file_growth.assert_not_called()
    manager.streamStarts['stream0'] = 270
    manager.check_stream('stream0', streamMock)
    streamMock.check_file_growth.assert_called_once()
    streamMock.should_record.return_value = False
    manager.check_stream('stream0', streamMock)
    assert streamMock.isActive == False

def test_check_fail_count(stream_manager):
    manager = stream_manager
    manager.check_fail_count()
    assert manager.corruptedUSBs == []

    cmdMock = mock.Mock()
    camMock = mock.Mock()

    camMock.consecutiveFailCount = 0
    cmdMock.consecutiveFailCount = 0
    manager.processes = {'stream0' : cmdMock, 'stream1' : camMock}
    manager.check_fail_count()
    assert manager.corruptedUSBs == []

    camMock.consecutiveFailCount = 3
    manager.storagePath = '/media/usb0'
    manager.check_fail_count()
    assert manager.corruptedUSBs == []

    cmdMock.consecutiveFailCount = 3
    camMock.consecutiveFailCount = 0
    manager.check_fail_count()
    assert manager.corruptedUSBs == []

    camMock.recordingSchedule = get_schedule_mock('always')
    cmdMock.consecutiveFailCount = 3
    camMock.consecutiveFailCount = 3
    manager.storagePath = '/media/usb0'
    manager.check_fail_count()
    assert manager.corruptedUSBs == ['/media/usb0']
    assert cmdMock.consecutiveFailCount == 0

    cmdMock.consecutiveFailCount = 3
    camMock.consecutiveFailCount = 3
    manager.corruptedUSBs = []
    manager.check_fail_count(changeDirAtFailCount=4)
    assert manager.corruptedUSBs == []

    manager.storagePath = '/i/am/not/mount'
    manager.check_fail_count()
    assert manager.corruptedUSBs == []

    cmdMock.consecutiveFailCount = 3
    camMock.consecutiveFailCount = 3
    manager.storagePath = '/mounted/storage0'
    manager.check_fail_count('/mounted/storage')
    assert manager.corruptedUSBs == ['/mounted/storage0']

@mock.patch('time.sleep')
@mock.patch(__name__ + '.' + 'dvrutils.format_size')
@mock.patch.object(stream.StreamManager, 'check_stream')
@mock.patch.object(stream.StreamManager, 'find_storage')
@mock.patch.object(stream.StreamManager, 'check_fail_count')
@mock.patch.object(stream.StreamManager, 'check_available_storage')
def test_check_stream_threads(avaiableMock, failMock, findMock, checkMock,
                             formatMock, sleepMock, stream_manager):
    manager = stream_manager
    manager.storageFull = True
    manager.strBytesFree = None
    manager.strSpaceNeeded = None
    manager.spaceNeeded = None
    manager.bytesFree = None
    avaiableMock.return_value = True
    manager.check_stream_threads()
    sleepMock.assert_called_once_with(5)
    findMock.assert_called_once()
    avaiableMock.return_value = False

    manager.check_stream_threads()
    failMock.assert_called_once()
    assert manager.storageFull == False
