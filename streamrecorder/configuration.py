import os
import re
import sys
import time
from configobj import ConfigObj
from copy import deepcopy
from socket import gethostname

sys.path.append('..')

from streamrecorder import dvrutils
from streamrecorder import schedule
from streamrecorder import sender
from streamrecorder import stream
from streamrecorder import tracker


class CameraInfo(object):
    """A class for managing camera URLs and credentials."""
    def __init__(self, manufacturer, streamType, user, passwd, formatUrl):
        self.manufacturer = manufacturer
        self.streamType = streamType
        self.user = user
        self.passwd = passwd
        self.formatUrl = formatUrl
        self.get_regex()
        
    def format_url(self, ip):
        return self.formatUrl.format(user=self.user,passwd=self.passwd,ipaddr=ip)
    
    def get_regex(self):
        try:
            regexDict = {'ipaddr' : r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',
                       'user' : self.user,
                       'passwd' : self.passwd}
            inBraces = False
            curlyBraceStr = ''
            regex = ''
            for c in self.formatUrl:
                if c == '{':
                    inBraces = True
                elif c == '}':
                    inBraces = False
                    regex += regexDict[curlyBraceStr]
                    curlyBraceStr = ''
                else:
                    if inBraces:
                        curlyBraceStr += c
                    else:
                        regex += c
            self.urlRegex = re.compile(regex)
        except:
            print('Could not parse {}'.format(self.formatUrl))
                

class ConfigurationHandler(object):
    
    def __init__(self, filename, appDir, logLevelArg=None):
        try:
            masterConfig = ConfigObj(filename)
        except:
            print ("Error reading master config file {}".format(filename))
            raise Exception('Invalid filename for master configurations')
        self.genParams = self.get_general_params(masterConfig)
        self.logLevel = self.genParams['loglevel'] if logLevelArg is None else logLevelArg
        self.ffmpegLogLevel = self.genParams['ffmpegloglevel'] if 'ffmpegloglevel' in self.genParams else None
        self.path = self.get_path()
        self.overwriteFiles = dvrutils.str_to_bool(self.genParams['storage']['overwritefiles'])
        self.minDaysOld = int(self.genParams['storage']['mindaysold'])
        self.execPath = __file__
        self.homeDir = os.environ['HOME']
        self.appDir =  appDir
        self.deviceName = gethostname()
        self.streamParams = {}
        self.create_logger() 
        self.cameraInfoDict = self.get_camera_info(self.genParams['camconfig'])
        self.streamConfig = self.get_stream_info(self.genParams['streamconfig'])
    
    def get_manager_and_sender(self):
        manager = self.create_manager()
        infoSender = self.create_sender(manager)
        return manager, infoSender

    def create_sender(self, manager):
        smTracker = tracker.StreamManagerTracker(manager, self.logger)
        senderInfo = self.get_sender_info()
        infoSender = sender.InformationSender(smTracker, senderInfo['user'], senderInfo['passwd'], 
                                              senderInfo['ip'], int(senderInfo['intervalMins']), self.logger)
        return infoSender

    def create_manager(self):
        if self.genParams['performrestarts']:
            streamManager = stream.StreamManager(self.deviceName, self.execPath, self.path, self.logger, self.logFilePath, 
                                              logLevel=self.logLevel, logLocation=self.logLocation,  
                                              overwriteFiles=self.overwriteFiles, minDaysOld=self.minDaysOld,
                                              initTime=15, performRestarts=True, onvifDir=self.genParams['onvifdir'], port=self.genParams['port'])
        else:    
            streamManager = stream.StreamManager(self.deviceName, self.execPath, self.path, self.logger, self.logFilePath, 
                                                  logLevel=self.logLevel, logLocation=self.logLocation,  
                                                  overwriteFiles=self.overwriteFiles, minDaysOld=self.minDaysOld,
                                                  initTime=15, performRestarts=False)
        if not self.streamParams:
            self.create_params_dict()
        for streamName, args in self.streamParams.items():
            if streamName != 'default':
                if args['type'] == 'command':
                    self.streamParams[streamName]['schedule'].print_recording_schedule(self.logger)
                    streamManager.add_command_stream(streamName, args['container'], args['commandStr'], args['schedule'])
                elif args['type'] == 'camera':
                    dvrutils.print_recording_params(self.logger, self.streamParams, streamName)
                    self.streamParams[streamName]['schedule'].print_recording_schedule(self.logger)
                    streamManager.add_video_stream(streamName, args['url'], args['container'], args['codec'], args['quality'],
                                                    args['framerate'], args['schedule'], self.ffmpegLogLevel, args['user'],
                                                    args['passwd'], args['manu'], args['ip'])
                else:
                    streamManager.add_video_stream(streamName, args['url'], args['container'], args['codec'], args['quality'],
                                                    args['framerate'], args['schedule'], self.ffmpegLogLevel, None)
        return streamManager

    def get_sender_info(self):
        senderDict = {}
        senderDict['user'] = self.genParams['sender']['user']
        senderDict['passwd'] = self.genParams['sender']['password']
        senderDict['ip'] = self.genParams['sender']['ip']
        senderDict['intervalMins'] = self.genParams['sender']['sendinterval']
        return senderDict

    def get_general_params(self, config):
        args = {}
        for key, value in config.items():
            if type(value) != str:
                args[key.lower()] = {}
                for k, v in config[key].items():
                    args[key.lower()][k.lower()] = v
            else:
                args[key.lower()] = value
        if 'performrestarts' in args:
            args['performrestarts'] = dvrutils.str_to_bool(args['performrestarts'])
        if 'port' in args:
            args['port'] = int(args['port'])
        else:
            args['port'] = None
        if 'onvifdir' not in args:
            args['onvifdir'] = None
        return args

    def get_path(self):
        storagePath = self.genParams['storage']['path']
        if dvrutils.storage_is_usb(storagePath):
            minBytesFree = 100000000  # assume we need at least 100 MB to do anything
            sPath = dvrutils.find_usb_storage(minBytesFree=minBytesFree)
            if sPath is not None:
                print ("Using USB storage at {}".format(sPath))
                storagePath = sPath
            else:
                print ("No USB storage space was found! Waiting for storage...")
                while sPath is None:
                    time.sleep(30)
                    sPath = dvrutils.find_usb_storage(minBytesFree=minBytesFree) # keep checking until something shows up
        return storagePath
    
    def create_logger(self):
        self.logLocation = os.path.join(self.appDir, 'logs')
        if not os.path.isdir(self.logLocation):
            if os.path.exists(self.logLocation):
                self.logLocation = dvrutils.get_unique_filename(self.logLocation,nZeros=0)
            print ("Log directory {} does not exist! Creating it now!".format(self.logLocation))
            os.makedirs(self.logLocation)
        self.logFilePath = os.path.join(self.logLocation, 'streamrecorder.log')            
        # TODO email alerts (need to work out networking issues)
        self.logger = dvrutils.setup_logging(self.logFilePath, self.logLevel, self.deviceName, 
                                             logToFile=True, logToStdout=True, logToEmail=False, toaddrs=None)
        self.logger.info("***** STREAMRECORDER START *****")
        self.logger.info("Logging at level {}".format(self.logLevel))

    def get_camera_config(self, camConfigFile):
        # first check storage, then homeDir, then appDir
        if os.path.exists(os.path.join(self.path, camConfigFile)):
            camConfigPath = os.path.join(self.path, camConfigFile)
        elif os.path.exists(os.path.join(self.homeDir, camConfigFile)):
            camConfigPath = os.path.join(self.homeDir, camConfigFile)
        elif os.path.exists(os.path.join(self.appDir, camConfigFile)):
            camConfigPath = os.path.join(self.appDir, camConfigFile)
        else:
            self.logger.error("Cannot find the camera configuration file {} in {}, {} or {}!".format(
                    camConfigFile, self.path, self.homeDir, self.appDir))
            raise Exception('Invalid camera configuration file name.')
        self.logger.info("Using camera configuration file {}".format(camConfigPath))
        try:
            return ConfigObj(camConfigPath)
        except:
            self.logger.critical("Error reading camera config file {}".format(camConfigPath))
            raise Exception('Invalid camera configuration file.')

    def get_camera_info(self, camConfigFile): 
        camConfig = self.get_camera_config(camConfigFile)
        defaultUser, defaultPasswd = '', ''
        for k, v in camConfig.items():
            if k not in camConfig.sections:
                if k.lower() == 'defaultuser':
                    defaultUser = v
                elif k.lower() == 'defaultpasswd':
                    defaultPasswd = v              
        cameraInfoDict = {}
        for manu in camConfig.sections:
            cameraInfoDict[manu] = {}
            for streamType in camConfig[manu].sections:
                user, passwd = defaultUser, defaultPasswd
                url = ''
                for k, v in camConfig[manu].items():
                    if k not in camConfig[manu].sections:
                        if k.lower() == 'user':
                            user = v
                        elif k.lower() == 'passwd':
                            passwd = v
                for k, v in camConfig[manu][streamType].items():
                    if k.lower() == 'user':
                        user = v
                    elif k.lower() == 'passwd':
                        passwd = v
                    elif k.lower() == 'url':
                        url = v
                if len(url) == 0:
                    self.logger.warning("No URL provided for {} cameras of stream type {}! This entry will be ignored!")
                cameraInfoDict[manu][streamType] = CameraInfo(manu, streamType, user, passwd, url)
        return cameraInfoDict

    def get_stream_info(self, streamConfigFile):
        # first check storage, then homeDir, then appDir
        if os.path.exists(os.path.join(self.path, streamConfigFile)):
            streamConfigPath = os.path.join(self.path, streamConfigFile)
        elif os.path.exists(os.path.join(self.homeDir, streamConfigFile)):
            streamConfigPath = os.path.join(self.homeDir, streamConfigFile)
        elif os.path.exists(os.path.join(self.appDir, streamConfigFile)):
            streamConfigPath = os.path.join(self.appDir, streamConfigFile)
        else:
            self.logger.error("Cannot find the stream configuration file {} in {} or {}!".format(
                    streamConfigFile, self.path, self.appDir))
            raise Exception('Invalid stream configuration file name.')
            # TODO: if the files aren't there, do something besides crashing
        self.logger.info("Using stream configuration file {}".format(streamConfigPath))
        try:
            return ConfigObj(streamConfigPath)
        except:
            self.logger.critical("Error reading stream config file {}".format(streamConfigPath))
            raise Exception('Invalid stream configuration file.')

    def get_default_video_params(self, streamConfig):
        defaultArgs = {}
        for k,v in streamConfig.items():
            if k.lower() != 'streams':
                defaultArgs[k.lower()] = v
        if 'schedule' in defaultArgs:
            defaultArgs['schedule'] = schedule.RecordingSchedule(scheduleString=defaultArgs['schedule'],
                                                            fileDurationMinutes=defaultArgs['filedurationminutes'])
        else: # record always if no schedule
            defaultArgs['schedule'] = schedule.RecordingSchedule(scheduleString='0000-2400', 
                                            fileDurationMinutes=defaultArgs['filedurationminutes'])
        defaultArgs['schedule'].print_recording_schedule(self.logger)
        return defaultArgs
                
    def get_camera_url(self, ip, manufacturer, streamType):
        sURL = ''
        if manufacturer in self.cameraInfoDict:
            if streamType in self.cameraInfoDict[manufacturer]:
                sURL = self.cameraInfoDict[manufacturer][streamType].format_url(ip)
            else:
                raise Exception('Stream type {} is not defined for {} camera!'.format(streamType, manufacturer))
        else:
            raise Exception('Camera manufacturer {} could not be found in the configuration file!'.format(manufacturer))
        return sURL

    def parse_options(self, optionStr):
        args = {}
        for option in optionStr.strip().strip('()').split(';'):
            try:
                k,v = [o.strip() for o in option.strip().split('=')]
                args[k.lower()] = v
            except:
                raise Exception("Failed to parse option {} in string {}".format(option, optionStr))
        return args

    def get_stream_options(self, schedStr='', optionStr=''):
        args = {}
        if optionStr != '':
            args = self.parse_options(optionStr)
            if schedStr.strip().lower() == 'default':
                schedStr = ''
            
        optionsList = ['container', 'codec', 'quality', 'framerate', 'filedurationminutes']
        for o in optionsList:
            if o not in args:
                args[o] = self.streamParams['default'][o]
        if schedStr == '':
            args['schedule'] = deepcopy(self.streamParams['default']['schedule'])
        else:
            args['schedule'] = schedule.RecordingSchedule(schedStr, args['filedurationminutes'])
        return args

    def determine_stream_type(self, values):
        ipRe = re.compile(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')
        firstElement = values[0] if type(values) == list else values
        if ipRe.match(firstElement) is not None:
            return 'paramCamera'
        elif len(firstElement) > 7 and firstElement[0:7] == 'http://' or firstElement[0:7] == 'rtsp://':
            return 'urlCamera'
        else:
            return 'command'
        
    def determine_camera_info(self, url):
        ipRe = re.compile(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
        try:
            ip = ipRe.findall(url)[0]
        except:
            raise Exception('Could not match ip in url: {}'.format(url))
        for manu, sTypeDict in self.cameraInfoDict.items():
            for key, info in sTypeDict.items():
                if info.urlRegex.match(url):
                    return info, ip

    def get_camera_with_params(self, streamName, streamCfg):
        args = {}
        try:
            args['type'] = 'camera'
            args['url'] = self.get_camera_url(streamCfg[0], streamCfg[1], streamCfg[2])
            if self.genParams['performrestarts']:
                info = self.cameraInfoDict[streamCfg[1]][streamCfg[2]]
                args['user'] = info.user
                args['passwd'] = info.passwd
                args['manu'] = info.manufacturer
                args['ip'] = streamCfg[0]
            else:
                args['user'] = None
                args['passwd'] = None
                args['manu'] = None
                args['ip'] = None
            schedStr, optionStr = '', ''
            if len(streamCfg) == 4:
                schedStr = streamCfg[3]
            elif len(streamCfg) == 5:
                schedStr, optionStr = streamCfg[3], streamCfg[4]
            elif len(streamCfg) > 5:
                raise Exception()
            args.update(self.get_stream_options(schedStr, optionStr))
        except:
            raise Exception('Could not parse {} as camera recorder without url.'.format(streamName))
        return args
   
    def get_camera_with_url(self, streamName, streamCfg):
        args = {}
        try:
            args['type'] = 'camera'
            schedStr, optionStr = '', ''
            if type(streamCfg) != list:
                args['url'] = streamCfg
            elif len(streamCfg) == 2:
                args['url'], schedStr = streamCfg
            elif len(streamCfg) == 3:
                args['url'], schedStr, optionStr = streamCfg
            else:
                raise Exception()
            args.update(self.get_stream_options(schedStr, optionStr))
            if self.genParams['performrestarts']:
                output = self.determine_camera_info(args['url'])
                info, ip = output
                args['user'] = info.user
                args['passwd'] = info.passwd
                args['manu'] = info.manufacturer
                args['ip'] = ip
            else:
                args['user'] = None
                args['passwd'] = None
                args['manu'] = None
                args['ip'] = None
        except:
            raise Exception('Could not parse {} as camera recorder with url.'.format(streamName))
        return args
    
    def get_command_params(self, streamName, streamCfg):
        args = {}
        try:
            args['type'] = 'command'
            schedStr, optionStr = '', ''
            if type(streamCfg) != list:
                args['commandStr'] = streamCfg
            elif len(streamCfg) == 2:
                args['commandStr'], schedStr = streamCfg
            elif len(streamCfg) == 3:
                args['commandStr'], schedStr, optionStr = streamCfg
            args.update(self.get_stream_options(schedStr, optionStr))
        except:
            raise Exception('Could not parse {} as command stream.'.format(streamName))
        return args

    def create_params_dict(self):
        self.streamParams['default'] = self.get_default_video_params(self.streamConfig)
        dvrutils.print_recording_params(self.logger, self.streamParams, 'default')
        for k in self.streamConfig.keys():
            if k.lower() == 'streams':
                streamKey = k
                break
        for streamName, streamCfg in self.streamConfig[streamKey].items():
            streamType = self.determine_stream_type(streamCfg)
            args = {}
            if streamType == 'paramCamera':
                args = self.get_camera_with_params(streamName, streamCfg)
            elif streamType == 'urlCamera':
                args = self.get_camera_with_url(streamName, streamCfg)
            elif streamType == 'command':
                args = self.get_command_params(streamName, streamCfg)
            else:
                self.logger.error('Could not determine stream type for {}!'.format(streamName))            
            if args != {}:
                self.streamParams[streamName] = args