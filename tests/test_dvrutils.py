import builtins
import os
import pytest
import shutil
import subprocess
import sys
import time
from unittest import mock

sys.path.append('..')

from streamrecorder import dvrutils

@mock.patch('subprocess.call')
def test_grabframe(callMock):
    callMock.return_value = 'call return'
    dvrutils.grabframe('url', 'imageName', 'info')
    callMock.assert_called_once_with(['ffmpeg','-loglevel','info','-y',
                                      '-rtsp_transport','tcp','-i','url',
                                      '-vframes','1','-q','1','imageName'])

def test_format_time():
    assert dvrutils.format_time(7317.5) == '02:01:57'
    assert dvrutils.format_time(7317.5, False) == '02:01'
    
def test_format_size():
    assert dvrutils.format_size(2306868) == '2.2MiB'
    
def test_longest_common_substring():
    assert dvrutils.longest_common_substring('abcdefgh', 'reibcdqpghpq') == 'bcd'
    assert dvrutils.longest_common_substring('1234abf', '77834afres') == '34a'
    
def test_print_recording_params():
    logMock = mock.Mock()
    vidParams = {'stream0' : {},
                 'stream1' : {'container' : 'avi',
                              'codec' : 'copy',
                              'framerate' : 15,
                              'quality' : 7,
                              'filedurationminutes' : 5,
                              'schedule': 'schedStr'}}
    dvrutils.print_recording_params(logMock, vidParams, 'stream1')
    logMock.info.assert_any_call('stream1 recording parameters:')
    logMock.info.assert_any_call('   Container: avi')
    logMock.info.assert_any_call('   Codec: copy')
    logMock.info.assert_any_call('   FrameRate: 15')
    logMock.info.assert_any_call('   Quality: 7')
    logMock.info.assert_any_call('   FileDuration: 5 minutes')
    logMock.info.assert_any_call('   Schedule: schedStr')

def test_setup_logging(): 
    logger = dvrutils.setup_logging('testFile.txt', 'INFO', 'deviceName')
    assert logger != None
    assert os.path.exists('testFile.txt')
    logger.info('Message')
    with open('testFile.txt', 'r') as f:
        line = f.readlines()[-1]
        assert 'deviceName' in line
        assert 'INFO' in line
        assert 'Message' in line
    logger.debug('SecondMessage')
    with open('testFile.txt', 'r') as f:
        for line in f.readlines():
            assert 'SecondMessage' not in line
    assert os.path.exists('testFile.txt')
    os.remove('testFile.txt')
    
def test_str_to_bool():
    assert dvrutils.str_to_bool('True') == True
    assert dvrutils.str_to_bool('true') == True
    assert dvrutils.str_to_bool('y') == True
    assert dvrutils.str_to_bool('1') == True
    assert dvrutils.str_to_bool('yes') == True
    assert dvrutils.str_to_bool('false') == False

@mock.patch('sys.argv')
@mock.patch('os.execv')    
@mock.patch('time.sleep')
def test_restart_program(sleepMock, execvMock, sysMock):
    dvrutils.restart_program('programName')
    sleepMock.assert_called_once_with(1)
    execvMock.assert_called_once_with('programName', sysMock)

@mock.patch('traceback.format_exc')
@mock.patch('time.strftime')  
@mock.patch('os.path.exists')
@mock.patch('os.makedirs') 
def test_log_fatal_error(makeMock, existsMock, strfMock, formatMock):
    existsMock.return_value = False
    with mock.patch('builtins.open', mock.mock_open()) as m:
        strfMock.return_value = 'filename.txt'
        formatMock.return_value = ''
        dvrutils.log_fatal_error('/path/to/dir')
        
        m.assert_called_once_with('/path/to/dir/crashlogs/filename.txt', 'a')
        makeMock.assert_called_with('/path/to/dir/crashlogs')
    
def test_storage_is_usb():
    assert dvrutils.storage_is_usb('/media/usb') == True
    assert dvrutils.storage_is_usb('/media/usb0/stream') == True
    assert dvrutils.storage_is_usb('/random/str') == False
    assert dvrutils.storage_is_usb('/words/usb') == False

@mock.patch('os.statvfs')
@mock.patch('os.path.ismount')
@mock.patch('os.path.exists')
@mock.patch(__name__ + '.' + 'dvrutils.get_disk_usage')
def test_find_usb_storage(diskMock, existsMock, mountMock, statvfsMock):
    
    def new_statvfs(path):
        infoMock = mock.Mock()
        infoMock.f_frsize = 10
        if path == '/media/usb2':
            infoMock.f_bavail = 10**7
        else:
            infoMock.f_bavail = 10**8
        return infoMock
    
    statvfsMock.side_effect = new_statvfs
    existsMock.return_value = False
    assert dvrutils.find_usb_storage() == None
    existsMock.side_effect = [True, True, True, True, False]
    mountMock.return_value = False
    assert dvrutils.find_usb_storage() == None
    diskMock.return_value = 10
    existsMock.side_effect = [True, True, True, True, False]
    mountMock.side_effect = [True, False, True, False]
    assert dvrutils.find_usb_storage() == None
    diskMock.return_value = 10**12
    existsMock.side_effect = [True, True, True, True, False]
    mountMock.side_effect = [True, False, True, False]
    assert dvrutils.find_usb_storage() == '/media/usb2'    
    
@mock.patch('os.path.exists')
@mock.patch('os.path.ismount')
@mock.patch('os.statvfs')
def test_get_disk_usage(statvfsMock, mountMock, existsMock):
    
    def new_statvfs(path):
        infoMock = mock.Mock()
        infoMock.f_frsize = 10
        infoMock.f_bavail = 30
        return infoMock
    
    statvfsMock.side_effect = new_statvfs
    existsMock.return_value = False
    assert dvrutils.get_disk_usage('path', True) == -1
    existsMock.return_value = True
    mountMock.return_value = False
    assert dvrutils.get_disk_usage('path', True) == -1
    assert dvrutils.get_disk_usage('path', False) == 300
    mountMock.return_value = True
    assert dvrutils.get_disk_usage('path', True) == 300
    
def test_get_unique_filename():
    assert dvrutils.get_unique_filename('test.txt') == 'test.txt'
    assert dvrutils.get_unique_filename('test_dvrutils.py') == 'test_dvrutils_00000.py'

@mock.patch('time.sleep')
def test_kill_process(sleepMock):
    processMock = mock.Mock()
    processMock.poll.return_value = 0
    loggerMock = mock.Mock()
    dvrutils.kill_process(processMock, loggerMock)
    processMock.terminate.assert_not_called()
    processMock.kill.assert_not_called()
    
    processMock.poll.side_effect = [None, 1, 1]
    dvrutils.kill_process(processMock, loggerMock)
    processMock.terminate.assert_called_once()
    processMock.kill.assert_not_called()
    
    processMock.terminate.reset_mock()
    processMock.poll.side_effect = [None, None, None]
    dvrutils.kill_process(processMock, loggerMock)
    processMock.terminate.assert_called_once()
    processMock.kill.assert_called_once()
    