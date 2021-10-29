import os, argparse
from configobj import ConfigObj

appDir = os.path.join(os.environ['HOME'],'streamrecorder')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__), usage='%(prog)s [options] [-s "StartHHMM-EndHHMM"] ["StreamDefinition"...]', description='Configure a computer running streamrecorder to record from one or more streams (manipulates the streams.cfg file). To set defaults, edit the FACTORYCONFIG file, or provide a different one with the corresponding flag.')
    parser.add_argument('streams', nargs='*', help = 'Stream definition string(s) for adding to the configuration. These must follow the same form of stream definitions in streams.cfg.')
    parser.add_argument('--reset', dest='resetConfig', action='store_true', help='Starts a new configuration file from nothing')    
    parser.add_argument('-s','--schedule', dest='defaultSchedule', help = 'Default schedule string to use.')
    parser.add_argument('-c','--container', dest='defaultContainer', help = 'Default container for video files.')
    parser.add_argument('-x','--codec', dest='defaultCodec', help = 'Default codec for encoding video files (can be \'copy\').')
    parser.add_argument('-q','--quality', dest='defaultQuality', help = 'Default quality of video files (only applies when codec is not \'copy\').')
    parser.add_argument('-r','--framerate', dest='defaultFramerate', help = 'Default framerate of video files created.')
    parser.add_argument('-d','--file-duration-minutes', dest='defaultFileDurationMinutes', help = 'Default duration of video files in minutes (must be a factor of 60).')
    parser.add_argument('-l', dest='testLength', help='The length of the test')
    parser.add_argument('-i', dest='interval', help='How often to check the streams and record data (in seconds)')
    parser.add_argument('-m', dest='minDaysOld', help='The minimum age (in days) of a file to delete')
    parser.add_argument('--storage', dest='storagePath', help = 'Path to video storage (set in mainConfigFile).')
    parser.add_argument('-f', dest='testConfigName', default='test.cfg', help='The name of the file to put the test configuation in')
    parser.add_argument('-o', dest='onvifDir', help='The name of the directory containing onvif')
    args = parser.parse_args()   

    # create config
    if not os.path.exists(args.testConfigName) or args.resetConfig:
        testConfig=ConfigObj()
        testConfig.filename = args.testConfigName
    else:
        testConfig=ConfigObj(args.testConfigName)
        
    if args.onvifDir is not None:
        testConfig['onvifdir'] = args.onvifDir
    else:
        testConfig['onvifdir'] = args.onvifDir
        

    # set length
    if args.testLength is not None:
        testConfig['length'] = args.testLength
    elif 'length' not in testConfig:
        testConfig['length'] = 300

    # set interval
    if args.interval is not None:
        testConfig['checkInterval'] = args.interval
    elif 'checkInterval' not in testConfig:
        testConfig['checkInterval'] = 5

    # set frame rate
    if args.defaultFramerate is not None:
        testConfig['FrameRate'] = args.defaultFramerate
    elif 'FrameRate' not in testConfig:
        testConfig['FrameRate'] = 15
        
    # set file duration minutes
    if args.defaultFileDurationMinutes is not None:
        testConfig['FileDurationMinutes'] = args.defaultFileDurationMinutes
    elif 'FileDurationMinutes' not in testConfig:
        testConfig['FileDurationMinutes'] = 3
        
    # set codec
    if args.defaultCodec is not None:
        testConfig['Codec'] = args.defaultCodec
    elif 'Codec' not in testConfig:
        testConfig['Codec'] = 'copy'

    # set quality
    if args.defaultQuality is not None:
        testConfig['Quality'] = args.defaultQuality
    elif 'Quality' not in testConfig:
        testConfig['Quality'] = 7

    # set schedule
    if args.defaultSchedule is not None:
        testConfig['Schedule'] = args.defaultSchedule
    elif 'Schedule' not in testConfig:
        testConfig['Schedule'] = 'always'        
    
    if 'Port' not in testConfig:
        testConfig['Port']=80
    
    # set storage
    if 'Storage' not in testConfig:
        testConfig['Storage'] = {}        
    
    if args.storagePath is not None:
        testConfig['Storage']['path'] = args.storagePath
    elif 'path' not in testConfig['Storage']:
        testConfig['Storage']['path'] = '/media/usb'
    
    if args.minDaysOld is not None:
        testConfig['Storage']['minDaysOld'] = args.minDaysOld
    elif 'minDaysOld' not in testConfig['Storage']:
        testConfig['Storage']['minDaysOld'] = 0        
        
    if 'mounted' not in testConfig['Storage']:
        testConfig['Storage']['mounted'] = True
    if 'overwriteFiles' not in testConfig['Storage']:
        testConfig['Storage']['overwriteFiles'] = True
    
    if 'Streams' not in testConfig:
        testConfig['Streams'] = {}
        
    for s in args.streams:
        parts = s.split('=')
        if ',' in parts[1]:
            testConfig['Streams'][parts[0]] = [w.strip() for w in parts[1].split(',')]
        else:
            testConfig['Streams'][parts[0]] = parts[1]
    testConfig.write()
