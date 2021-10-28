#!/usr/bin/python3

#============================================================
# Standard Modules (always in Python, with exception of dvrutils)
#------------------------------------------------------------
import os
import time
import argparse
import traceback
#------------------------------------------------------------
# End Standard Modules
#============================================================
from streamrecorder import dvrutils        # needs to be there to log an error, if this can't import, it's a critical error that should have been fixed during the last upgrade (the one that presumably broke it)
#============================================================
# Program Constants
#------------------------------------------------------------
configFilename = "streamrecorder.cfg"                                # file path of configuration file, looks in same (application) directory
embeddedLogDirectory = "crashlogs"                                   # directory to use for storing embedded logs (program crashes), looks in same (application) directory
execPath = __file__
appDir = os.path.abspath(os.path.dirname(__file__))                                  # get directory of program so we can be explicit about using it or the storage directory
homeDir = os.environ['HOME']                                         # the user's home directory

# run everything in try block so any exceptions can be dumped to the embedded logfile
if __name__ == "__main__":
    argparseHelpExit = False
    try:
        # Custom/3rd Party Modules (must be included or installed beforehand)
        from configobj import ConfigObj
        from streamrecorder import configuration
        import streamrecorder.schedule
        import streamrecorder.stream
        
        # Argument Parsing
        parser = argparse.ArgumentParser(prog='streamrecorder.py', usage='%(prog)s [-c configFile]', description='Records video from predefined camera streams with a configurable schedule and duration.')
        parser.add_argument('-l', '--loglevel', dest = 'loglevel', default = 'INFO', help = '(Optional) streamrecorder log level (does not affect FFMPEG log level). Specify numeric values (10, 20, 30, etc.) or strings like DEBUG or WARNING') # TODO: different log levels for file and stream?
        parser.add_argument('-c', dest='configFilename', default='streamrecorder.cfg')
        
        try:
            args = parser.parse_args()      # TODO: argparse bug here when help is used, how to fix?
        except SystemExit as e:
            # if we get a normal SystemExit exception here set a flag and re-raise
            if e.code == 0:
                argparseHelpExit = True
            raise
        
        config = configuration.ConfigurationHandler(
                args.configFilename, appDir, args.loglevel)
        streamManager, infoSender = config.get_manager_and_sender()
        streamManager.start_streams()
        
        # TODO run videoarchiver.py here somewhere
        
        # keep watching the threads, restarting them if they end (scheduling, etc. handled by streamManager)
        while True:
            streamManager.check_stream_threads()                     # checks all threads, restarting them if they stop
            infoSender.check_sender()
            time.sleep(1) # sleeps an additional 5 seconds in check_stream_threads
        
    except:
        # don't log anything if argparse had us exit
        if not argparseHelpExit:
            # if something broke, log it to a crashlog file and print it to the screen
            print(traceback.format_exc())
            dvrutils.log_fatal_error(appDir, embeddedLogDirectory)