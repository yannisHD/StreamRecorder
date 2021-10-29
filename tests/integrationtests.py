import datetime
import os
import requests
import time
import shutil
import sys
from configobj import ConfigObj

from streamrecorder import dvrutils
from streamrecorder import schedule
from streamrecorder import stream


def get_camera_connections():
    config = ConfigObj('pytest.cfg')
    onvifDir = config['onvifdir']
    sys.path.append(onvifDir)
    from onvif import ONVIFCamera
    connections = {}
    for name, values in config['OnvifCameras'].items():
        connections[name] = ONVIFCamera(values[0], config['port'], config['user'], config['passwd'], os.path.join(onvifDir, 'wsdl'))
    return connections 

def pytest_generate_tests(metafunc):
    config = ConfigObj('pytest.cfg')
    connections = get_camera_connections()
    if 'onvifdir' in metafunc.fixturenames:
        metafunc.parametrize('onvifdir', [config['onvifdir']])
    if 'onvifCams' in metafunc.fixturenames:
        cams = []
        for key, values in config['OnvifCameras'].items():
            cams.append(values + [config['user'], config['passwd'], config['port'], connections[key]])
        metafunc.parametrize('onvifCams', cams)
    if 'axisCams' in metafunc.fixturenames:
        cams = []
        for key, values in config['AxisCameras'].items():
            cams.append(values + [config['user'], config['passwd'], config['port']])
        metafunc.parametrize('axisCams', cams)
        

def test_set_camera_time(onvifdir, onvifCams):
    recorder = stream.CameraRecorder('dvrName', 'stream0', 'http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi',
                                     'avi', 'copy', 7, 15, schedule.RecordingSchedule('always'), 'storage')
    camera = onvifCams[6] # contains connection to camera
    time_params = camera.devicemgmt.create_type('SetSystemDateAndTime')
    rightNow = datetime.datetime.now()
    time_params.DateTimeType = 'Manual'
    time_params.DaylightSavings = True
    time_params['UTCDateTime'] = {}
    time_params['UTCDateTime']['Date'] = {}
    time_params['UTCDateTime']['Time'] = {}
    time_params['UTCDateTime']['Date']['Year'] = 2010
    time_params['UTCDateTime']['Date']['Month'] = 6
    time_params['UTCDateTime']['Date']['Day'] = rightNow.day
    time_params['UTCDateTime']['Time']['Hour'] = rightNow.hour
    time_params['UTCDateTime']['Time']['Minute'] = rightNow.minute
    time_params['UTCDateTime']['Time']['Second'] = rightNow.second
    camera.devicemgmt.SetSystemDateAndTime(time_params)
    recorder.set_camera_time(camera)
    dt = camera.devicemgmt.GetSystemDateAndTime()
    assert dt.UTCDateTime.Date.Year == rightNow.year

def test_onvif_camera_restart(onvifdir, onvifCams):
    recorder = stream.CameraRecorder('dvrName', 'stream0', 'http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi',
                                     'avi', 'copy', 7, 15, schedule.RecordingSchedule('always'), 'storage')
    camera = onvifCams[6] # contains connection to camera
    recorder.manufacturer = onvifCams[1]
    recorder.user = onvifCams[3]
    recorder.passwd = onvifCams[4]
    recorder.ip = onvifCams[0]
    recorder.port = onvifCams[5]
    recorder.onvifDir = onvifdir
    recorder.camera_restart(1)
    assert recorder.continueRecordingPast > time.time()
    restarting = False
    i = 0
    while not restarting and i < 60:
        try:
            camera.devicemgmt.GetSystemDateAndTime() # just checking for a response
        except:
            restarting = True
        time.sleep(1)
        i += 1
        print(i)
    assert restarting
    time.sleep(60) # avoid error when there are too many requests at once
    
def test_fts_camera_restart(axisCams):
    recorder = stream.CameraRecorder('dvrName', 'stream0', 'http://username:pass@10.179.1.252/axis-cgi/mjpg/video.cgi',
                                     'avi', 'copy', 7, 15, schedule.RecordingSchedule('always'), 'storage')
    recorder.manufacturer = axisCams[1]
    recorder.user = axisCams[3]
    recorder.passwd = axisCams[4]
    recorder.ip = axisCams[0]
    recorder.fts_restart(1)
    assert recorder.continueRecordingPast < time.time()
    status = 200
    i = 0
    while status == 200 and i < 60:
        print(i)
        i += 1
        try:
            r = requests.get('http://{}:{}@{}/axis-cgi/jpg/image.cgi'.format(axisCams[3], axisCams[4], axisCams[0]), # args: user, passwd, ip
                             auth=(axisCams[3], axisCams[4]))
            status = r.status_code
            time.sleep(1)
        except:
            status = 0
    assert status != 200
    time.sleep(60) # avoid error when there are too many requests at once

def test_camera_record():
    if os.path.exists('storage'):
        shutil.rmtree('storage')
    os.mkdir('storage')
    recorder = stream.CameraRecorder('dvrName', 'stream0', 'http://username:***REMOVED***@10.179.1.252/axis-cgi/mjpg/video.cgi',
                                     'avi', 'copy', 7, 15, schedule.RecordingSchedule('always', 2), 'storage')
    recordStart = datetime.datetime.now()
    recorder.record()
    recordEnd = datetime.datetime.now()
    assert len(os.listdir('storage')) == 1
    file = os.listdir('storage')[0]
    assert 'dvrName_stream0' == file[:15]
    assert '.avi' == file[-4:]
    date = file[16:24]
    assert date == time.strftime('%Y%m%d')
    stimestr = file[25:31]
    etimestr = file[32:38]
    stime = datetime.datetime.strptime(date+stimestr, '%Y%m%d%H%M%S')
    etime = datetime.datetime.strptime(date+etimestr, '%Y%m%d%H%M%S')
    assert datetime.timedelta(-1, 86390) < stime-recordStart < datetime.timedelta(0, 10)
    assert datetime.timedelta(-1, 86390) < etime-recordEnd < datetime.timedelta(0, 10)
    shutil.rmtree('storage')
    
def test_command_record():
    if os.path.exists('storage'):
        shutil.rmtree('storage')
    os.mkdir('storage')
    recorder = stream.CommandRecorder('dvrName', 'stream1', 'storage', 'txt', 
                                      'python writefile.py -f {filename}', 
                                      schedule.RecordingSchedule('always', 2))
    recordStart = datetime.datetime.now()
    recorder.record()
    recordEnd = datetime.datetime.now()
    assert len(os.listdir('storage')) == 1
    file = os.listdir('storage')[0]
    assert 'dvrName_stream1' == file[:15]
    assert '.txt' == file[-4:]
    date = file[16:24]
    assert date == time.strftime('%Y%m%d')
    stimestr = file[25:31]
    etimestr = file[32:38]
    stime = datetime.datetime.strptime(date+stimestr, '%Y%m%d%H%M%S')
    etime = datetime.datetime.strptime(date+etimestr, '%Y%m%d%H%M%S')
    assert datetime.timedelta(-1, 86390) < stime-recordStart < datetime.timedelta(0, 10)
    assert datetime.timedelta(-1, 86390) < etime-recordEnd < datetime.timedelta(0, 10)
    shutil.rmtree('storage')
    

def test_grabframe(onvifCams):
    dvrutils.grabframe('rtsp://username:***REMOVED***@10.179.1.249/ufirststream', 'testImage.avi', 'info')
    assert os.path.isfile('testImage.avi')
    os.remove('testImage.avi')