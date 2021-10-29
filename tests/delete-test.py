#!/usr/bin/python3
import argparse
import sys
import os
import time
from configobj import ConfigObj

import testutils

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='filename', default='test.cfg')
    args = parser.parse_args()
    
    exit_code = 0 # 0 if nothing unexpected has happened, else 1

    testConfig = ConfigObj(args.filename)
    streams = testutils.create_cfg_files(testConfig)
    testLength = int(testConfig['length'])
    fileDurationMinutes = int(testConfig['FileDurationMinutes']) if 'FileDurationMinutes' in testConfig else 60
    checkInterval = 5    
    
    testutils.rewrite_dvrutils(10000000000)
    process, thread = testutils.run_streamrecorder()
    stime = time.time() # start time   
    prev_size = 0
    startUsage = testutils.get_disk_usage('/mnt/video')
    print('Waiting for files to fill...')
    
    # keep doing checks until streamrecorder starts deleting files
    while time.time() < stime + 3600 * 24:
        sizes = []
        time.sleep(checkInterval)
        for s in streams:
            total_size = sum([os.path.getsize(s[2] + '/' + f) for f in os.listdir(s[2])])
            sizes.append(total_size)
        if prev_size > sum(sizes):
            break
        prev_size = sum(sizes)
        
    if time.time() >= stime + 3600 * 24 - 1:
        print ('Files never started gettting deleted, exitting...')
        sys.exit(1)
    
    print('Storage full, starting test...')
    newStime = time.time()
    lastFiles = {}
    currFiles = {}
    fileDirs = {}
    errorCount = 0
    for s in streams:
        lastFiles[s[0]] = set(os.path.join(s[2], f) for f in os.listdir(s[2]))
    while time.time() < newStime + testLength:
        time.sleep(checkInterval)
        try: # in case files get renamed/deleted midloop
            for s in streams:
                currFiles[s[0]] = set(os.path.join(s[2], f) for f in os.listdir(s[2]))
            avgSize = {}
            totalSize = {}
            for s in streams:
                totalSize[s[0]] = sum([os.path.getsize(f) for f in currFiles[s[0]]])
                avgSize[s[0]] = totalSize[s[0]] / len(currFiles[s[0]])
            streamSizes = [value for _, value in totalSize.items()]
            avgStreamSize = sum(streamSizes) / len(streamSizes)
            for s in streams:
                deletedFiles = set(lastFiles[s[0]]) - set(currFiles[s[0]])
                removeFiles = set()
                for d in deletedFiles:
                    for c in currFiles:
                        if d[:-11] in c:
                            print('removing {}'.format(d))
                            removeFiles.add(d)
                            break
                for r in removeFiles:
                    deletedFiles.remove(r)
                if deletedFiles != set():
                    if totalSize[s[0]] + avgSize[s[0]] * 4 < avgStreamSize:
                        print ('Error stream {} deleted files while not being the largest stream.'.format(s[0]))
                        exit_code = 1
            lastFiles = dict(currFiles)
        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            errorCount += 1
            if errorCount > 3:
                raise e
    sys.exit(exit_code)