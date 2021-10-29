import os
import pytest
import re
import sys
from configobj import ConfigObj
from unittest import mock

sys.path.append('..')

from streamrecorder import configuration
from streamrecorder import dvrutils
from streamrecorder import schedule
from streamrecorder import sender
from streamrecorder import stream

# =============================================================================
# CameraInfo Tests
# =============================================================================

@pytest.fixture
def camera_info():
    return configuration.CameraInfo('Axis', 'MJPEG', 'username', 'pass', 'http://{user}:{passwd}@{ipaddr}/axis-cgi/mjpg/video.cgi')

def test_camerainfo_ctor():
    info = camera_info()
    assert info.manufacturer == 'Axis'
    assert info.streamType == 'MJPEG'
    assert info.user == 'username'
    assert info.passwd == 'pass'
    assert info.formatUrl == 'http://{user}:{passwd}@{ipaddr}/axis-cgi/mjpg/video.cgi'
    assert info.urlRegex != None
    
def test_format_url():
    info = camera_info()
    assert info.format_url('10.179.1.252') == 'http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi'
    
def test_get_regex():
    info = camera_info()
    regex = info.urlRegex
    assert regex.match('http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi')
    assert not regex.match('http://user:pass@10.179.1.252/axis-cgi/mjpg/video.cgi')
    assert regex.match('http://username:pass@12.10.11.25/axis-cgi/mjpg/video.cgi')
    assert not regex.match('http://username:pass@12.9999.11.25/axis-cgi/mjpg/video.cgi')

# =============================================================================
# Configuration Handler Tests
# =============================================================================
    
@mock.patch('streamrecorder.configuration.gethostname')
@mock.patch(__name__ + '.' + 'dvrutils.str_to_bool')
@mock.patch.object(configuration.ConfigurationHandler, 'get_path')
@mock.patch.object(configuration.ConfigurationHandler, 'get_general_params')
@mock.patch.object(configuration.ConfigurationHandler, 'create_logger')
@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_info')
@mock.patch.object(configuration.ConfigurationHandler, 'get_stream_info')
def create_handler(streamMock, camMock, logMock, genMock, pathMock, boolMock, hostMock):
    genMock.return_value = {'storage' : {'mindaysold' : 3, 'overwritefiles' : True,
                                         'path' : '/mnt/video'},
                            'sender' : {'user':'username', 'password':'pass',
                                        'ip':'10.179.1.2', 'sendinterval':'7'},
                            'camconfig' : 'cam.cfg', 'streamconfig' : 'stream.cfg',
                            'loglevel' : 'info', 'ffmpegloglevel' : 'error',
                            'performrestarts' : True, 'onvifdir' : '/home/username/onvif',
                            'port' : 80}
    pathMock.return_value = '/mnt/video'
    boolMock.return_value = True
    hostMock.return_value = 'dvrName'
    handler = configuration.ConfigurationHandler('streamrecorder.cfg', '..')
    handler.logger = mock.Mock()
    handler.logLocation = 'logLoc'
    handler.logFilePath = 'logPath'
    return handler

@mock.patch('streamrecorder.configuration.gethostname')
@mock.patch(__name__ + '.' + 'dvrutils.str_to_bool')
@mock.patch.object(configuration.ConfigurationHandler, 'get_path')
@mock.patch.object(configuration.ConfigurationHandler, 'get_general_params')
@mock.patch.object(configuration.ConfigurationHandler, 'create_logger')
@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_info')
@mock.patch.object(configuration.ConfigurationHandler, 'get_stream_info') 
def test_ctor(streamMock, camMock, logMock, genMock, pathMock, boolMock, hostMock):
    genMock.return_value = {'storage' : {'mindaysold':3, 'overwritefiles':True},
                            'sender' : {'user':'username', 'passwd':'pass',
                                        'ip':'10.179.1.2', 'sendinterval':'7'},
                            'camconfig' : 'cam.cfg', 'streamconfig' : 'stream.cfg',
                            'loglevel' : 'info', 'ffmpegloglevel' : 'error'}
    hostMock.return_value = 'dvrName'
    pathMock.return_value = '/mnt/video'
    boolMock.return_value = True
    handler = configuration.ConfigurationHandler('streamrecorder.cfg', '..')
    assert handler.logLevel == 'info'
    assert handler.ffmpegLogLevel == 'error'
    assert handler.path == '/mnt/video'
    assert handler.overwriteFiles == True
    assert handler.minDaysOld == 3
    assert handler.homeDir == os.environ['HOME']
    assert os.path.abspath(handler.appDir) == \
            os.path.abspath(os.path.dirname(__file__) +'/..')
    assert handler.deviceName == 'dvrName'
    logMock.assert_called_once()
    camMock.assert_called_once()
    streamMock.assert_called_once()
    try:
        configuration.ConfigurationHandler('fake.cfg')
        assert 0
    except:
        pass

@mock.patch('streamrecorder.stream.StreamManager')
def test_create_manager(initMock):
    handler = create_handler()
    loggerMock = mock.Mock()
    smMock = mock.Mock()
    schedDefault = mock.Mock()
    sched0 = mock.Mock()
    sched1 = mock.Mock()
    initMock.return_value = smMock
    handler.logger = loggerMock
    handler.streamParams = {'default' : {
            'container':'avi', 'framerate':'15', 'fileduarionmiuntes':'5',
            'codec':'copy','quality':'7', 'schedule':schedDefault},
        'stream0':{'type':'camera','url':'streamUrl', 'user':'username', 'passwd':'pass',
                   'manu':'Axis', 'ip':'10.179.1.252','container':'avi','codec':'copy',
                   'quality':'7', 'framerate':'15', 'filedurationminutes':'5',
                   'schedule':sched0},
        'stream1':{'type':'command', 'commandStr':'python writefile.py -f {filename}',
                   'container':'txt', 'codec':'copy', 'quality':'7', 'framerate':'15',
                   'filedurationminutes':'5','schedule':sched1}}
    handler.create_manager()
    initMock.assert_called_once_with('dvrName', handler.execPath, '/mnt/video', loggerMock,
        'logPath', initTime=15, logLevel='info', logLocation='logLoc', minDaysOld=3,
        onvifDir='/home/username/onvif', overwriteFiles=True, performRestarts=True, port=80)
    smMock.add_video_stream.assert_called_once_with('stream0', 'streamUrl', 'avi', 'copy', '7', '15',
        sched0, 'error', 'username', 'pass', 'Axis', '10.179.1.252')
    smMock.add_command_stream.assert_called_once_with('stream1', 'txt', 'python writefile.py -f {filename}',
                                                      sched1)
    sched0.print_recording_schedule.assert_called_once()
    sched1.print_recording_schedule.assert_called_once()
    schedDefault.print_recording_schedule.assert_not_called()

@mock.patch('streamrecorder.tracker.StreamManagerTracker')
@mock.patch('streamrecorder.sender.InformationSender')
@mock.patch.object(configuration.ConfigurationHandler, 'get_sender_info')    
def test_create_sender(infoMock, sendMock, trackMock):
    handler = create_handler()
    trackerMock = mock.Mock()
    managerMock = mock.Mock()
    loggerMock = mock.Mock()
    infoMock.return_value = {'user':'username','passwd':'pass','ip':'10.179.1.128',
                             'intervalMins':'7'}
    sendMock.return_value = 'infoSender'
    trackMock.return_value = trackerMock
    handler.logger = loggerMock
    assert handler.create_sender(managerMock) == 'infoSender'
    sendMock.assert_called_once()
    trackMock.assert_called_once_with(managerMock, loggerMock)
    sendMock.assert_called_once_with(trackerMock, 'username', 'pass', '10.179.1.128',
                                     7, loggerMock)

@mock.patch.object(configuration.ConfigurationHandler, 'create_sender')
@mock.patch.object(configuration.ConfigurationHandler, 'create_manager')    
def test_get_manager_and_sender(managerMock, senderMock):
    handler = create_handler()
    managerMock.return_value = 'created manager'
    senderMock.return_value = 'created sender'
    assert handler.get_manager_and_sender() == ('created manager', 'created sender')
    managerMock.assert_called_once()
    senderMock.assert_called_once_with('created manager')
    
def test_get_sender_info():
    handler = create_handler()
    senderDict = handler.get_sender_info()
    assert senderDict['user'] == 'username'
    assert senderDict['passwd'] == 'pass'
    assert senderDict['ip'] == '10.179.1.2'
    assert senderDict['intervalMins'] == '7'

@mock.patch(__name__ + '.' + 'dvrutils.str_to_bool')        
def test_get_general_params(strToBoolMock): # TODO: finish testing the rest of the control structures
    
    def new_str_to_bool(word):
        if word.lower() == 'true':
            return True
        return False
    
    strToBoolMock.side_effect = new_str_to_bool
    handler = create_handler()
    config = ConfigObj('unittestStreamrecorder.cfg')
    args = handler.get_general_params(config)
    for key, value in args.items():
        if type(value) == dict:
            for k, v in value.items():
                assert k.islower() or k.isdigit
        else:
            assert key.islower()
    assert args['ffmpegloglevel'] == 'error'
    assert args['port'] == 80
    assert args['camconfig'] == 'tests/unittestCamerainfo.cfg'
    assert args['streamconfig'] == 'tests/unittestStreams.cfg'
    assert args['performrestarts'] == True
    assert args['onvifdir'] == '/home/username/onvif'
    assert args['storage']['path'] == '/mnt/video'
    assert args['storage']['overwritefiles'] == 'True'
    assert args['storage']['mindaysold'] == '3'
    assert args['storage']['mounted'] == 'True'
    assert args['sender']['user'] == 'username'
    assert args['sender']['password'] == 'passwd'
    assert args['sender']['ip'] == '10.179.1.2'
    assert args['sender']['sendinterval'] == '3'

@mock.patch(__name__ + '.' + 'dvrutils.storage_is_usb')  
def test_get_path(isUsbMock):
    handler = create_handler()
    isUsbMock.return_value = False
    assert handler.get_path() == '/mnt/video'

@mock.patch(__name__ + '.' + 'dvrutils.setup_logging')
@mock.patch(__name__ + '.' + 'dvrutils.get_unique_filename')
@mock.patch('os.makedirs')
@mock.patch('os.path.exists')
@mock.patch('os.path.isdir')                       
def test_create_logger(isdirMock, existsMock, makeMock, uniqueMock, setupLogMock):
    handler = create_handler()
    handler.appDir = 'appDir'
    isdirMock.return_value = True
    handler.create_logger()
    assert handler.logLocation == 'appDir/logs'
    assert handler.logFilePath == 'appDir/logs/streamrecorder.log'
    setupLogMock.assert_called_with('appDir/logs/streamrecorder.log', 'info',
        'dvrName', logToFile=True, logToStdout=True, logToEmail=False, toaddrs=None)
    makeMock.assert_not_called()
    
    isdirMock.return_value = False
    existsMock.return_value = False
    handler.create_logger()
    makeMock.assert_called_once()
    assert handler.logLocation == 'appDir/logs'
    assert handler.logFilePath == 'appDir/logs/streamrecorder.log'
    setupLogMock.assert_called_with('appDir/logs/streamrecorder.log', 'info',
        'dvrName', logToFile=True, logToStdout=True, logToEmail=False, toaddrs=None)
    
    isdirMock.return_value = False
    existsMock.return_value = True
    uniqueMock.return_value = 'unique/path'
    makeMock.reset_mock()
    handler.create_logger()
    makeMock.assert_called_once()
    assert handler.logLocation == 'unique/path'
    assert handler.logFilePath == 'unique/path/streamrecorder.log'
    setupLogMock.assert_called_with('unique/path/streamrecorder.log', 'info',
        'dvrName', logToFile=True, logToStdout=True, logToEmail=False, toaddrs=None)

@mock.patch('streamrecorder.configuration.ConfigObj')
@mock.patch('os.path.exists')
def test_get_camera_config(existsMock, objMock):
    handler = create_handler()
    handler.path = 'path'
    handler.homeDir = 'homeDir'
    handler.appDir = 'appDir'
    existsMock.return_value = False
    with pytest.raises(Exception):
        handler.get_camera_config('name')
    
    existsMock.return_value = True
    handler.get_camera_config('name')
    objMock.assert_called_with('path/name')
    
    existsMock.side_effect = [False, True]
    handler.get_camera_config('name')
    objMock.assert_called_with('homeDir/name')
    
    existsMock.side_effect = [False, False, True]
    handler.get_camera_config('name')
    objMock.assert_called_with('appDir/name')

@mock.patch('streamrecorder.configuration.CameraInfo')
@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_config')
def test_get_camera_info(camConfigMock, infoMock):
    handler = create_handler()
    camConfigMock.return_value = ConfigObj( {'DefaultUser':'username', 
        'DefaultPasswd':'pass',
        'Axis' : {'RTSP':{'url':'AxisRTSPurl'}, 
                  'MJPEG':{'url':'AxisMJPEGurl'}},
        'General':{'Passwd':'genPass','RTSP':{'url':'GeneralRTSPurl'}}})
    infoDict = handler.get_camera_info('filename')
    assert 'MJPEG' in infoDict['Axis']
    assert 'RTSP' in infoDict['Axis']
    assert 'RTSP' in infoDict['Axis']
    infoMock.assert_any_call('Axis', 'MJPEG', 'username', 'pass', 'AxisMJPEGurl')
    infoMock.assert_any_call('Axis', 'RTSP', 'username', 'pass', 'AxisRTSPurl')
    infoMock.assert_any_call('General', 'RTSP', 'username', 'genPass', 'GeneralRTSPurl')

@mock.patch('streamrecorder.configuration.ConfigObj')
@mock.patch('os.path.exists') 
def test_get_stream_info(existsMock, objMock):
    handler = create_handler()
    handler.path = 'path'
    handler.homeDir = 'homeDir'
    handler.appDir = 'appDir'
    existsMock.return_value = False
    with pytest.raises(Exception):
        handler.get_stream_info('name')
    
    existsMock.return_value = True
    handler.get_stream_info('name')
    objMock.assert_called_with('path/name')
    
    existsMock.side_effect = [False, True]
    handler.get_stream_info('name')
    objMock.assert_called_with('homeDir/name')
    
    existsMock.side_effect = [False, False, True]
    handler.get_stream_info('name')
    objMock.assert_called_with('appDir/name')
   
def test_get_camera_url():
    handler = create_handler()
    axisMJPEGMock = mock.Mock()
    axisMJPEGMock.format_url.return_value = 'AxisMJPEG'
    axisRTSPMock = mock.Mock()
    axisRTSPMock.format_url.return_value = 'AxisRTSP'
    ganzRTSPMock = mock.Mock()
    ganzRTSPMock.format_url.return_value = 'GanzRTSP'
    handler.cameraInfoDict = {'Axis':{'MJPEG':axisMJPEGMock, 'RTSP':axisRTSPMock},
                              'Ganz':{'RTSP':ganzRTSPMock}}
    assert handler.get_camera_url('10.179.1.252', 'Axis', 'MJPEG') == 'AxisMJPEG'
    
    with pytest.raises(Exception):
        handler.get_camera_url('10.179.1.252', 'Unknown', 'MJPEG')
        
    with pytest.raises(Exception):
        handler.get_camera_url('10.179.1.252', 'Axis', 'Unknown')
    
def test_parse_options():
    handler = create_handler()
    for i in range(5):
        handler.streamParams['stream{}'.format(i)]={}
    assert handler.parse_options('(quality=6)')  == {'quality' : '6'}
    assert handler.parse_options('(framerate=30;filedurationminutes=1;codec=diff)') == \
        {'framerate' : '30', 'filedurationminutes' : '1', 'codec' : 'diff'}
    assert handler.parse_options('(fileDurationMinutes=10;frameRate=1)') == \
        {'filedurationminutes' : '10', 'framerate' : '1'}
    assert handler.parse_options(' ( Container = mp4 ; FrameRate = 5 ) ') == \
        {'container' : 'mp4','framerate' : '5'}
    assert handler.parse_options('   (  QuaLItY   =  6  ;    FrAmErAtE=30;   '
                               +'FILEDURATIONMINUTES =6; COdeC = DIFF     )  ') == \
        {'quality' : '6', 'framerate' : '30', 'codec' : 'DIFF', 'filedurationminutes' : '6'}

def test_determine_camera_info():
    handler = create_handler()
    axisMJPEGMock = mock.Mock()
    axisMJPEGMock.urlRegex.match.return_value = False
    axisRTSPMock = mock.Mock()
    axisRTSPMock.urlRegex.match.return_value = False
    ganzRTSPMock = mock.Mock()
    ganzRTSPMock.urlRegex.match.return_value = False
    handler.cameraInfoDict = {'Axis':{'MJPEG':axisMJPEGMock, 'RTSP':axisRTSPMock},
                              'Ganz':{'RTSP':ganzRTSPMock}}
    with pytest.raises(Exception):
        handler.determine_camera_info('url')
    assert handler.determine_camera_info('rtsp://username:wrongpass@10.179.1.252/axis-media/media.amp') == None
    axisRTSPMock.urlRegex.match.return_value = True
    assert handler.determine_camera_info('rtsp://username:pass@10.179.1.252/axis-media/media.amp') == (axisRTSPMock, '10.179.1.252')

@mock.patch('streamrecorder.schedule.RecordingSchedule')
def test_get_default_video_params(schedMock):
    handler = create_handler()
    streamConfig = {'framerate':'15','filedurationminutes':'5', 'codec':'copy', 'quality':'7',
                            'streams':{'stream0':'params','stream1':'params'}}
    defaults = handler.get_default_video_params(streamConfig)
    assert defaults['framerate'] == '15'
    assert defaults['filedurationminutes'] == '5'
    assert defaults['codec'] == 'copy'
    assert defaults['quality'] == '7'
    assert 'streams' not in defaults
    assert 'stream0' not in defaults
    schedMock.assert_called_with(scheduleString='0000-2400', fileDurationMinutes='5')
    streamConfig['schedule'] = 'Mon:1200-1300'
    handler.get_default_video_params(streamConfig)
    schedMock.assert_called_with(scheduleString='Mon:1200-1300', fileDurationMinutes='5')

@mock.patch('streamrecorder.configuration.deepcopy')
@mock.patch('streamrecorder.schedule.RecordingSchedule')
def test_get_stream_options(schedMock, deepCopyMock):
    handler = create_handler()
    handler.streamParams['default'] = {'filedurationminutes':'5', 'quality':'7',
                        'codec':'copy','container':'avi','framerate':'15',
                        'schedule':'defaultSchedule'}
    args0 = handler.get_stream_options()
    deepCopyMock.assert_called_once_with('defaultSchedule')
    schedMock.assert_not_called()
    assert args0['quality'] == '7'
    assert args0['container'] == 'avi'
    assert args0['framerate'] == '15'
    assert args0['filedurationminutes'] == '5'
    
    deepCopyMock.reset_mock()
    args1 = handler.get_stream_options('Thu:0000-1000')
    schedMock.assert_called_once_with('Thu:0000-1000', '5')
    assert args1['quality'] == '7'
    assert args1['container'] == 'avi'
    assert args1['framerate'] == '15'
    assert args1['filedurationminutes'] == '5'
    
    schedMock.reset_mock()
    args2 = handler.get_stream_options('default', '(Container=txt;quality=6)')
    deepCopyMock.assert_called_once_with('defaultSchedule')
    schedMock.assert_not_called()
    assert args2['quality'] == '6'
    assert args2['container'] == 'txt'
    assert args2['framerate'] == '15'
    assert args2['filedurationminutes'] == '5'
    
    args3 = handler.get_stream_options('1000-2000', '(fileDurationMinutes=3;frameRate=10)')
    schedMock.assert_called_with('1000-2000', '3')
    assert args3['quality'] == '7'
    assert args3['container'] == 'avi'
    assert args3['framerate'] == '10'
    assert args3['filedurationminutes'] == '3'

def test_determine_stream_type():
    handler = create_handler()
    assert handler.determine_stream_type(['10.179.1.252', 'Axis', 'MJPEG']) == 'paramCamera'
    assert handler.determine_stream_type('http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi') == 'urlCamera'
    assert handler.determine_stream_type(['http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi', 'always']) == 'urlCamera'
    assert handler.determine_stream_type('rtsp://ipaddr:8554/h264') == 'urlCamera'
    assert handler.determine_stream_type(['rtsp://ipaddr:8554/h264', 'Wed:1000-1200', '(quality=1)']) == 'urlCamera'
    assert handler.determine_stream_type(['python -f {filename} program.py']) == 'command'
    assert handler.determine_stream_type(['sleep 10']) == 'command'

@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_url')
@mock.patch.object(configuration.ConfigurationHandler, 'get_stream_options')
def test_get_camera_with_params(optionMock, urlMock):
    handler = create_handler()
    handler.streamParams['default'] = {'filedurationminutes':'5', 'quality':'7',
                    'codec':'copy','container':'avi','framerate':'15',
                    'schedule':'defaultSchedule'}
    axisMJPEGMock = mock.Mock()
    axisRTSPMock = mock.Mock()
    ganzRTSPMock = mock.Mock()
    handler.cameraInfoDict = {'Axis':{'MJPEG':axisMJPEGMock, 'RTSP':axisRTSPMock},
                              'Ganz':{'RTSP':ganzRTSPMock}}
    optionMock.return_value = {'quality' : '7', 'framerate' : '15'}
    
    handler.genParams['performrestarts'] = False
    args0 = handler.get_camera_with_params('stream0', ['10.179.1.252', 'Axis', 'MJPEG'])
    optionMock.assert_called_with('', '')
    urlMock.assert_called_with('10.179.1.252', 'Axis', 'MJPEG')
    assert args0['type'] == 'camera'
    assert args0['user'] == None
    assert args0['passwd'] == None
    assert args0['manu'] == None
    assert args0['ip'] == None
    assert args0['quality'] == '7'
    
    handler.genParams['performrestarts'] = True
    ganzRTSPMock.user = 'username'
    ganzRTSPMock.passwd = 'pass'
    ganzRTSPMock.manufacturer = 'Ganz'
    args1 = handler.get_camera_with_params('stream1', ['111.111.111.111', 'Ganz', 'RTSP', 'Fri:1000-2000'])
    optionMock.assert_called_with('Fri:1000-2000', '')
    urlMock.assert_called_with('111.111.111.111', 'Ganz', 'RTSP')
    assert args1['type'] == 'camera'
    assert args1['user'] == 'username'
    assert args1['passwd'] == 'pass'
    assert args1['manu'] == 'Ganz'
    assert args1['ip'] == '111.111.111.111'
    assert args1['framerate'] == '15'
    
    handler.genParams['performrestarts'] = False
    handler.get_camera_with_params('stream2', ['123.123.213.189', 'Axis', 'RTSP', 'Sun:0000-0100', '(filedurationminutes=1)'])
    optionMock.assert_called_with('Sun:0000-0100', '(filedurationminutes=1)')
    urlMock.assert_called_with('123.123.213.189', 'Axis', 'RTSP')
    
    with pytest.raises(Exception):
        handler.get_camera_with_params('stream3', ['10.179.1.252', 'Axis'])
        
    with pytest.raises(Exception):
        handler.get_camera_options('stream2', ['123.123.213.189', 'Axis', 'RTSP', 'Sun:0000-0100', '(filedurationminutes=1)', 'sixth'])
        
    handler.genParams['performrestarts'] = True
    with pytest.raises(Exception):
        handler.get_camera_with_params('stream4', ['10.179.1.252', 'Unknown', 'RTSP'])

@mock.patch.object(configuration.ConfigurationHandler, 'determine_camera_info')
@mock.patch.object(configuration.ConfigurationHandler, 'get_stream_options')
def test_get_camera_with_url(optionMock, infoMock):
    handler = create_handler()
    handler.streamParams['default'] = {'filedurationminutes':'5', 'quality':'7',
                    'codec':'copy','container':'avi','framerate':'15',
                    'schedule':'defaultSchedule'}
    returnMock = mock.Mock()
    returnMock.user = 'username'
    returnMock.passwd = 'pass'
    returnMock.manufacturer = 'man'
    infoMock.return_value = (returnMock, '10.179.1.252')
    optionMock.return_value = {'quality' : '7', 'framerate' : '15'}
    
    handler.genParams['performrestarts'] = True
    args0 = handler.get_camera_with_url('stream0', 'http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi')
    optionMock.assert_called_with('', '')
    infoMock.assert_called_with('http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi')
    assert args0['user'] == 'username'
    assert args0['passwd'] == 'pass'
    assert args0['manu'] == 'man'
    assert args0['ip'] == '10.179.1.252'
    assert args0['quality'] == '7'
    
    handler.genParams['performrestarts'] = False
    args1 = handler.get_camera_with_url('stream1', ['rtsp://username:pass@10.179.1.249/ufirststream', 'Sat:1000-1500'])
    optionMock.assert_called_with('Sat:1000-1500', '')
    assert args1['user'] == None
    assert args1['manu'] == None
    assert args1['passwd'] == None
    assert args1['ip'] == None
    assert args1['framerate'] == '15'
    
    handler.get_camera_with_url('stream2', ['rtsp://127.0.0.1:8554/h264', 'default', '(quality=6)'])
    optionMock.assert_called_with('default', '(quality=6)')
    
    with pytest.raises(Exception):
        handler.get_camera_with_url('stream3', ['rtsp://127.0.0.1:8554/h264', 'default', '(quality=6)', 'fourth'])

@mock.patch.object(configuration.ConfigurationHandler, 'get_stream_options')
def test_get_command_params(optionMock):
    handler = create_handler()
    handler.streamParams['default'] = {'filedurationminutes':'5', 'quality':'7',
                    'codec':'copy','container':'avi','framerate':'15',
                    'schedule':'defaultSchedule'}
    optionMock.return_value = {'container' : 'txt', 'filedurationminutes' : '5'}
    
    args0 = handler.get_command_params('stream0', 'python -f {filename} filemaker.py')
    optionMock.assert_called_with('', '')
    assert args0['container'] == 'txt'
    
    args1 = handler.get_command_params('stream1', ['sleep 10', '1000-1100'])
    optionMock.assert_called_with('1000-1100', '')
    assert args1['filedurationminutes'] == '5'
    
    handler.get_command_params('stream2', ['python makefile.py', 'Tue:0930-1000', '(container=csv)'])
    optionMock.assert_called_with('Tue:0930-1000', '(container=csv)')

@mock.patch(__name__ + '.' + 'dvrutils.print_recording_params')
@mock.patch.object(configuration.ConfigurationHandler, 'get_command_params')
@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_with_url')
@mock.patch.object(configuration.ConfigurationHandler, 'get_camera_with_params')
@mock.patch.object(configuration.ConfigurationHandler, 'determine_stream_type')
def test_create_params_dict(determineMock, camParamMock, camUrlMock, cmdMock, printMock):
    
    def new_determine_stream_type(streamCfg):
        if type(streamCfg) != list:
            return 'urlCamera'
        elif len(streamCfg) == 4:
            return 'paramCamera'
        else:
            return 'command'
    
    handler = create_handler()
    handler.streamConfig = {'framerate':'15','filedurationminutes':'5', 'codec':'copy', 'quality':'7',
                            'streams':{'stream0':['arg0','arg1','arg2', 'arg3'],
                                       'stream1':'arg0',
                                       'stream2':['arg0', 'arg1']}}
    determineMock.side_effect = new_determine_stream_type
    camParamMock.return_value = 'camParamArgs'
    camUrlMock.return_value = 'camUrlArgs'
    cmdMock.return_value = 'cmdArgs'
    handler.create_params_dict()
    assert handler.streamParams['stream0'] == 'camParamArgs'
    assert handler.streamParams['stream1'] == 'camUrlArgs'
    assert handler.streamParams['stream2'] == 'cmdArgs'
    camParamMock.assert_called_with('stream0', ['arg0','arg1','arg2', 'arg3'])
    camUrlMock.assert_called_with('stream1', 'arg0')
    cmdMock.assert_called_with('stream2', ['arg0', 'arg1'])