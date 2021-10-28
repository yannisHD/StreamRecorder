#!/usr/bin/python

import os, sys, argparse
import streamrecorder.dvrutils as dvrutils
from copy import deepcopy
from configobj import ConfigObj

appDir = os.path.join(os.environ['HOME'],'streamrecorder')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__), usage='%(prog)s [options] [-s "StartHHMM-EndHHMM"] ["StreamDefinition"...]', description='Configure a computer running streamrecorder to record from one or more streams (manipulates the streams.cfg file). To set defaults, edit the FACTORYCONFIG file, or provide a different one with the corresponding flag.')
    parser.add_argument('streams', nargs='*', help = 'Stream definition string(s) for adding to the configuration. These must follow the same form of stream definitions in streams.cfg.')
    parser.add_argument('-l','--list', dest='listStreams', action = 'store_true', help = 'List streams in the current configuration.')
    parser.add_argument('-p','--print', dest='printConfig', action = 'store_true', help = 'Print the current configuration in its entirety.')
    parser.add_argument('-hh', '--more-help', dest='moreHelp', action = 'store_true', help = 'Print help information from the streams.cfg file for more information on how to format inputs.')
    parser.add_argument('--reset', dest='resetConfig', action = 'store_true', help = 'Reset the configuration found in CONFIGFILE to the \'factory\' state as defined in FACTORYCONFIG.')
    parser.add_argument('--clear', dest='clearStreams', action = 'store_true', help = 'Clear all streams defined in the config file.')
    parser.add_argument('-R','--remove', dest='removeStream', nargs='+', help='Remove the stream(s) with the specified name(s), if it exists in the file.')
    parser.add_argument('-s','--schedule', dest='defaultSchedule', help = 'Default schedule string to use.')
    parser.add_argument('-c','--container', dest='defaultContainer', help = 'Default container for video files.')
    parser.add_argument('-x','--codec', dest='defaultCodec', help = 'Default codec for encoding video files (can be \'copy\').')
    parser.add_argument('-q','--quality', dest='defaultQuality', help = 'Default quality of video files (only applies when codec is not \'copy\').')
    parser.add_argument('-r','--framerate', dest='defaultFramerate', help = 'Default framerate of video files created.')
    parser.add_argument('-d','--file-duration-minutes', dest='defaultFileDurationMinutes', help = 'Default duration of video files in minutes (must be a factor of 60).')
    parser.add_argument('--storage', dest='storagePath', help = 'Path to video storage (set in mainConfigFile).')
    parser.add_argument('-f','--config', dest='configFile', default = os.path.join(os.environ['HOME'],'streams.cfg'), help = 'Path to the streams.cfg file to use (default: %(default)s).')
    parser.add_argument('-t','--test-config', dest='testConfig', action = 'store_true', help = 'Run the entire script (currently, only checks if storage path is valid, but will be expanded).')
    parser.add_argument('--factory-config', dest='factoryConfig', default = os.path.join(appDir,'streams.cfg'), help = 'Path to the streams.cfg file to use for \'factory default\' settings (default: %(default)s).')
    parser.add_argument('--main-config', dest='mainConfigFile', default = os.path.join(appDir,'streamrecorder.cfg'), help = 'Path to the streamrecorder.cfg file to use for storage and logging settings  (default: %(default)s).')
    args = parser.parse_args()
    
    if not os.path.exists(args.factoryConfig):
        print ("Error! Could not find the factory config {}! The installation may be damaged!".format(args.factoryConfig))
        sys.exit(1)
        
    # parse the factory config
    factoryCfg = ConfigObj(args.factoryConfig)
    
    # if they need more help, print the config header and exit
    if args.moreHelp:
        for l in factoryCfg.initial_comment:
            print (l)
        sys.exit(0)
        
    # if they wanted us to reset the configuration, ask if they are sure then delete the file
    if args.resetConfig:
        if os.path.exists(args.configFile):
            if dvrutils.yesno("Are you sure you want to reset the configuration? This cannot be undone! [y/N]"):
                print ("Removing existing configuration in file {}".format(args.configFile))
                os.remove(args.configFile)
            else:
                sys.exit(1)
        else:
            print ("Configuration {} does not exist! Cannot remove empty configuration!".format(args.configFile))
                
    # parse the current config
    if not os.path.exists(args.configFile):
        print ("Creating config file {} now from factory config!".format(args.configFile))
        cfg = deepcopy(factoryCfg)
        cfg.filename = args.configFile
        cfg.write()
    else:
        cfg = ConfigObj(args.configFile)
    
    # check the storage path in the main config
    mainCfg = ConfigObj(args.mainConfigFile)
    sPath = mainCfg['Storage']['path']
    path1, path2 = '/mnt/video', '/media/usb'           # TODO generalize this
    editConfig = False
    
    # print the streams if requested
    if args.listStreams:
        print ("Streams defined in {}:".format(args.configFile))
        if len(cfg['Streams']) == 0:
            print (' None')
        for sn, sd in cfg['Streams'].iteritems():
            print (" {}: {}".format(sn, sd))
        sys.exit(0)
    
    # print the whole config if requested
    if args.printConfig:
        if args.storagePath is None:
            print ("Storage path in main config file {} is {}".format(args.mainConfigFile, sPath))
        print ("Configuration located in file {}:".format(args.configFile))
        for k, v in cfg.iteritems():
            if k != 'Streams':
                print (" {}: {}".format(k, v))
            else:
                print (" Streams:")
                if len(cfg['Streams']) == 0:
                    print ('  None')
                for sn, sd in cfg['Streams'].iteritems():
                    print ("  {}: {}".format(sn, sd))
        sys.exit(0)
    
    # edit the config
    paramsEdited, editedConfig = '', False
    if args.defaultSchedule is not None:
        cfg['Schedule'] = args.defaultSchedule
        paramsEdited += "Changing Schedule to {}\n".format(args.defaultSchedule)
    if args.defaultContainer is not None:
        cfg['Container'] = args.defaultContainer
        paramsEdited += "Changing Container to {}\n".format(args.defaultContainer)
    if args.defaultCodec is not None:
        cfg['Codec'] = args.defaultCodec
        paramsEdited += "Changing Codec to {}\n".format(args.defaultCodec)
    if args.defaultQuality is not None:
        cfg['Quality'] = args.defaultQuality
        paramsEdited += "Changing Quality to {}\n".format(args.defaultQuality)
    if args.defaultFramerate is not None:
        cfg['FrameRate'] = args.defaultFramerate
        paramsEdited += "Changing FrameRate to {}\n".format(args.defaultFramerate)
    if args.defaultFileDurationMinutes is not None:
        cfg['FileDurationMinutes'] = args.defaultFileDurationMinutes
        paramsEdited += "Changing FileDurationMinutes to {}\n".format(args.defaultFileDurationMinutes)
        
    # remove stream if requested
    if args.removeStream is not None:
        for sn in args.removeStream:
            if sn in cfg['Streams']:
                paramsEdited += "Removing stream '{}' from file ...\n".format(sn)
                del cfg['Streams'][sn]
            else:
                print ("Stream '{}' not in config!".format(sn))
    
    # clear all streams if requested
    if args.clearStreams:
        paramsEdited += "Clearing existing streams from file ...\n"
        cfg['Streams'] = {}
        
    if len(paramsEdited) > 0:
        editedConfig = True
        print (paramsEdited.strip())
        
    if args.streams is not None:
        for ss in args.streams:
            sn, sd = [s.strip() for s in ss.split('=')]
            sdef = [s.strip() for s in sd.split(',')]
            print ("Adding stream {} with definition {}".format(sn, sdef))
            cfg['Streams'][sn] = sdef
            editedConfig = True
        
    if editedConfig:
        print ("Writing changes to config file {}...".format(cfg.filename))
        cfg.write()
    
    # change storage path if requested
    if args.storagePath is not None:
        print ("Changing storage path in file {} to {} as per user request".format(args.mainConfigFile, args.storagePath))
        storagePath = args.storagePath
        if not os.path.exists(storagePath):
            editConfig = dvrutils.yesno("Storage path {} does not exist! Are you sure you want to set this as the storage path? [y/N]")
        else:
            editConfig = True
    
    # if the path does not exist and it is one of our standard paths, try the other one to see if it will work
    elif not os.path.exists(sPath):
        print ("Storage path {} does not exist! This is probably a mistake, attempting to correct it now!".format(sPath))
        newPath = sPath
        if path1 in sPath and os.path.exists(path2):
            newPath = path2
        elif path2 in sPath and os.path.exists(path1):
            newPath = path1
        if newPath == sPath:
            print ("No known storage paths exist! This could not be corrected!")
        else:
            print ("Storage path will be changed to {}!".format(newPath))
            storagePath = newPath
            editConfig = True
        
    # write the changes if any were made
    if editConfig:
        print ("Writing changes to config file {}...".format(args.mainConfigFile))
        mainCfg['Storage']['path'] = storagePath
        mainCfg.write()
    
