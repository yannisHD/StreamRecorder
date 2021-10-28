#!/usr/bin/python

import os, sys, time, glob, argparse
import subprocess
import dvrutils, srconfig
from socket import gethostname

appDir = os.path.join(os.environ['HOME'],'streamrecorder')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grab frames from all the streams defined in the config file streamConfig.")
    parser.add_argument('streamConfig', help="Name of the file containing streams to check.")
    parser.add_argument('-o', dest='outputDir', default='frames', help="Directory in which to place output frames (default: %(default)s).")
    parser.add_argument('-d', dest='dateTimeFormat', default='%Y%m%d_%H%M%S', help="Datetime format string to use for naming the output files (default: %(default)s).")
    parser.add_argument('--master-config', dest='masterConfig', help="Path to the master streamrecorder configuration file (for overriding the default).")
    args = parser.parse_args()
    
    # load the configuration if it exists
    if not os.path.exists(args.streamConfig):
        print "File '{}' does not exist! Exiting!".format(args.streamConfig)
        sys.exit(1)
    cfg = srconfig.getConfig(args.masterConfig, streamConfigFile=args.streamConfig)
    
    # make sure streams are defined before doing anything
    if len(cfg.streamUrls.keys()) == 0:
        print "No streams defined in file '{}' ! Exiting!".format(args.streamConfig)
        sys.exit(2)
    
    # make the output directory
    print "Outputting frames to directory '{}' ...".format(args.outputDir)
    if not os.path.exists(args.outputDir):
        os.makedirs(args.outputDir)
    
    # get frames
    for sName in cfg.streamUrls.keys():
        sUrl = cfg.streamUrls[sName]
        outputImage = os.path.join(args.outputDir, "{}_{}.jpg".format(sName, time.strftime(args.dateTimeFormat)))
        print "Putting frame from stream '{}' into file '{}' ...".format(sName, outputImage)
        dvrutils.grabframe(sUrl, outputImage)
    