#!/usr/bin/python

import os, sys, time, glob
import threading, argparse
from collections import OrderedDict
from math import floor
import subprocess

def format_size(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def repeatString(s, num):
    ss = ""
    for i in range(0,num):
        ss += s
    return ss

class FileWatch(object):
    """A class representing a watch on a growing file.
       Currently this is limited to regular checks of 
       the file's size and calculating the growth rate,
       but more functions can be added."""
    
    # CONSTANTS
    defaultInterval = 5
    defaultWindow = 5
    defaultGapOut = 10
       
    def __init__(self, fname, showMtime=False, checkInterval=defaultInterval, smoothWindow=defaultWindow, gapOutTime=defaultGapOut, printFullPath=False):
        self.name = fname
        self.showMtime = showMtime
        self.checkInterval = checkInterval
        self.smoothWindow = smoothWindow
        self.gapOutTime = gapOutTime
        self.printFullPath = printFullPath
        self.reset()
        self.start()
        
    def __repr__(self):
        activeStr = 'Active' if self.active else 'Inactive'
        fnstr = self.name if self.printFullPath else os.path.basename(self.name)
        if self.exists:
            s = "<FileWatch ({active}) [{name}]: {size}, {rate}/s".format(active=activeStr, name=self.name, size=format_size(self.currSize), rate=format_size(self.growthRate))
            if self.showMtime:
                s += "({mtime})".format(mtime=self.mtime)
            s += '>'
        else:
            s = "<FileWatch ({active}) [{name}]: File does not exist>".format(active=activeStr, name=self.name)
        return s
    
    def __str__(self):
        fnstr = self.name if self.printFullPath else os.path.basename(self.name)
        if self.exists:
            return "{name}: {size}, {rate}/s".format(name=fnstr, size=format_size(self.currSize), rate=format_size(self.growthRate))
        return None
    
    def reset(self, checkInterval=defaultInterval, smoothWindow=defaultWindow, gapOutTime=defaultGapOut):
        self.exists = False
        self.sizes = OrderedDict({time.time(): 0})
        self.currSize = 0
        self.mtime = None
        self.growthRate = 0
        self.lastChange = 0
        self.checkInterval = checkInterval
        self.smoothWindow = smoothWindow
        self.gapOutTime = gapOutTime
        
    def check(self):
        exists = os.path.exists(self.name)
        if exists:
            self.exists = exists
            self.mtime = os.path.getmtime(self.name)
            self.currSize = os.path.getsize(self.name)
            self.sizes[time.time()] = self.currSize
            self.calcGrowthRate()
        elif exists and not self.exists:
            self.lastChange = time.time()
        self.timeSinceChange = time.time() - self.lastChange
    
    def calcGrowthRate(self):
        if self.smoothWindow > len(self.sizes):
            self.lastSizeTime = self.sizes.keys()[0]
        else:
            self.lastSizeTime = self.sizes.keys()[-self.smoothWindow]
        self.lastSize = self.sizes[self.lastSizeTime]
        t = floor(time.time() - self.lastSizeTime)
        self.growthRate = (self.currSize - self.lastSize)/t if t > 0 else self.currSize
        if self.growthRate != 0:
            self.lastChange = time.time()
        
    def watch(self, checkInterval=None, gapOutTime=None):
        self.active = True
        if checkInterval is not None:
            self.checkInterval = checkInterval
        if gapOutTime is not None:
            self.gapOutTime = gapOutTime
        while self.active:
            self.check()
            time.sleep(self.checkInterval)
            if self.timeSinceChange >= self.gapOutTime:
                self.stop()     # gap out if hasn't grown for too long
    
    def start(self, checkInterval=None, gapOutTime=None):
        self.thread = threading.Thread(target=self.watch, kwargs={'checkInterval': checkInterval, 'gapOutTime': gapOutTime})
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        self.active = False
    
    def isActive(self):
        self.timeSinceChange = time.time() - self.lastChange
        if self.timeSinceChange >= self.gapOutTime:
            self.stop()
        return self.active
    
    def isAlive(self):
        return self.thread.isAlive()
    
class DirWatch(object):
    """A class representing a watch on an entire directory of files.
       This will watch all files in a directory and keep track of 
       files that are currently changing (i.e. they have changed
       in the last X seconds)."""
    def __init__(self, dname, fileTypes=['*'], maxFileAge=30, scanInterval=10, fileCheckInterval=5, smoothWindow=5, gapOutTime=10, printFullPath=False):
        self.directory = dname
        self.fileTypes = fileTypes
        self.maxFileAge = maxFileAge
        self.scanInterval = scanInterval
        self.fileCheckInterval = fileCheckInterval
        self.smoothWindow = smoothWindow
        self.gapOutTime = gapOutTime
        self.printFullPath = printFullPath
        self.files = []
        self.fwatches = OrderedDict()
        self.start()
        
    def __repr__(self):
        return "<DirWatch> [{name}]: {nfiles} files being watched>".format(name=self.directory, nfiles=len(fwatches))
        
    def scanForFiles(self):
        """Add new files to the watch list"""
        # get a list of files
        nowish = time.time()        # now, minus whatever time has passed since we started looping
        for ft in self.fileTypes:
            ftlist = glob.glob(os.path.join(self.directory,ft))
            for f in ftlist:
                # make a watch for each of the most recently modified files
                if f not in self.fwatches:
                    mtime = os.path.getmtime(f)
                    fage = nowish - mtime
                    if fage < self.maxFileAge:
                        self.fwatches[f] = FileWatch(f, checkInterval=self.fileCheckInterval, smoothWindow=self.smoothWindow, gapOutTime=self.gapOutTime, printFullPath=self.printFullPath)
    
    def watch(self, scanInterval=None):
        self.active = True
        if scanInterval is not None:
            self.scanInterval = scanInterval
        while self.active:
            self.scanForFiles()
            time.sleep(self.scanInterval)
    
    def start(self, scanInterval=None):
        self.thread = threading.Thread(target=self.watch, kwargs={'scanInterval': scanInterval})
        self.thread.daemon = True
        self.thread.start()
        
    def printWatches(self, printDirName=False):
        if printDirName:
            print "{dname}:".format(dname=self.directory)
        for fn in sorted(self.fwatches.keys()):
            fw = self.fwatches[fn]
            print fw
            if not fw.isActive():
                self.fwatches.pop(fn)       # remove inactive watches from the list
        
if __name__ == "__main__":
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Watch growing files in a list of directories.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('directories', nargs='+', help='Direcory/list of directories to watch.')
    parser.add_argument('-f', dest='fileTypes', nargs='*', help='File types to look for (defaults to *)')
    parser.add_argument('-i', dest='updateInt', type=int, default=2, help='Time interval in seconds between screen updates')
    parser.add_argument('-m', dest='maxFileAge',type=int, default=30, help='Maximum age of files to consider when scanning')
    parser.add_argument('-s', dest='scanInterval', type=int, default=10, help='Time to wait before scanning for files again')
    parser.add_argument('-c', dest='fileCheckInterval', type=int, default=5, help='Time between file size samples')
    parser.add_argument('-w', dest='smoothWindow', type=int, default=5, help='Number of check intervals back to take value for calculating growth')
    parser.add_argument('-g', dest='gapOutTime', type=int, default=10, help='Amount of time to wait before dropping files that have stopped changing.')
    parser.add_argument('-a', dest='printFullPath', action='store_true', help='Print the entire file path')
    args = parser.parse_args()
    dlist = args.directories if len(args.directories) > 0 else [os.getcwd()]        # default to cwd
    ftypes = ['*.*'] if args.fileTypes is None else args.fileTypes
    
    # make all our directory watches
    dwatches = []
    for d in dlist:
        dwatches.append(DirWatch(d, fileTypes=ftypes, maxFileAge=args.maxFileAge, scanInterval=args.scanInterval, fileCheckInterval=args.fileCheckInterval, smoothWindow=args.smoothWindow, gapOutTime=args.gapOutTime, printFullPath=args.printFullPath))
    
    # wait for a few seconds, then watch them forever
    time.sleep(2)
    while True:
        tStr = time.strftime(' %H:%M:%S %b %d %Y ')
        nrows, ncols = subprocess.check_output(['stty', 'size']).split()        # read the terminal size
        ncols = int(ncols)
        ndashes = ncols - len(tStr) - 2                                         # calculate how many dashes we need
        leftSide = repeatString('-', ndashes/2)                                 # round LHS down from ndashes/2
        rightSide = leftSide = repeatString('-', ndashes-len(leftSide))         # put remainder on RHS
        print leftSide + tStr + rightSide
        for d in dwatches:
            d.printWatches()
        time.sleep(args.updateInt)
        