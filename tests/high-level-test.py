#!/usr/bin/python3
import argparse
import datetime
import os
import threading
import time
import sqlite3
import sys

from collections import defaultdict
from configobj import ConfigObj
from multiprocessing.pool import ThreadPool
from socket import gethostname

import testutils


# watches file growth for the files in its directory
class DirectoryWatcher:

    def __init__(self, stream, startTime, interval=5, tlength=300, noGrowthError=6):
        self.dirName = stream[2] + '/'
        self.stream = stream
        self.stime = startTime
        self.check_interval = interval
        self.end_time = time.time() + tlength
        self.files = {}
        self.lastFiles = set(os.listdir(self.dirName)) if os.path.exists(self.dirName) else set()
        self.noGrowthError = noGrowthError # number consecutive times of no growth to report not growing
        self.noGrowthCount = 0
        self.stime = time.time()
        self.start()

    def stop(self):
        self.active = False

    def watch(self):
        self.active = True
        while self.active:
            time.sleep(self.check_interval)            
            growing = False
            for f in os.listdir(self.dirName):
                f = self.dirName + f
                if f not in self.files:
                    self.files[f] = [(time.strftime('%Y/%m/%d %H:%M:%S'), os.stat(f).st_size, 0)]
                    growing = True
                elif os.stat(f).st_size != self.files[f][-1][1]:
                    self.files[f].append((time.strftime('%Y/%m/%d %H:%M:%S'), os.stat(f).st_size, self.files[f][-1][1]))
                    growing = True
            if self.should_be_growing() == False:
                growing = True
            if growing:
                self.noGrowthCount = 0
            else:
                self.noGrowthCount += 1

            if time.time() > self.end_time:
                self.stop()

    def start(self):
        for i in range(10): # wait for files to be created
            if os.path.exists(self.dirName):
                break
            time.sleep(1)
        else:
            raise Exception('File {} was not created'.format(self.dirName))
        for f in os.listdir(self.dirName):
            f = self.dirName + f
            self.files[f] = [(time.strftime('%Y/%m/%d %H:%M:%S'), os.stat(f).st_size, 0)]   
        self.thread = threading.Thread(target=self.watch)
        self.thread.daemon = True
        self.thread.start()
        
    def should_be_growing(self):
        duration = int(self.stream[3]['filedurationminutes'])
        if time.time() % (duration * 60) < 20 or time.time() % (duration * 60) > duration * 60 - 5:
            return False
        if self.stream[1] == 'test': # if recording schedule is test
            if time.time() >= int((self.stime // 60)) * 60 + 355:
                return False
            if int((self.stime // 60)) * 60 + 115 <= time.time() <= int((self.stime // 60) * 60) + 260:
                return False
        elif self.stream != 'always':
            return False
        else:
            return True

    def get_deleted_file_info(self):
        currFiles = os.listdir(self.dirName)
        deletedFiles = set(self.lastFiles) - set(currFiles)
        removeFiles = set()
        for d in deletedFiles:
            for c in currFiles:
                if d[:-11] in c:
                    removeFiles.add(d)
                    break
        for r in removeFiles:
            deletedFiles.remove(r)
        fileSizes = [os.path.getsize(os.path.join(self.dirName , f)) for f in currFiles]
        totalSize = sum(fileSizes)
        if len(fileSizes) > 0:
            avgSize = sum(fileSizes) / len(fileSizes)
        else:
            avgSize = 0
        self.lastFiles = set(currFiles)
        return deletedFiles, totalSize, avgSize

    def check_status(self):
        return self.noGrowthCount < self.noGrowthError
    
    # Return dict: key=streamName, values=list of tuples containing date&time (yyyy/mm/dd hh:mm:ss), current size, growth rate from previous interval to current interval
    def get_statistics(self):
        return dict(self.files)

#==============================================================================
# Main Function
#==============================================================================

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='filename', default='test.cfg')
    args = parser.parse_args()

    exit_code = 0 # 0 if nothing unexpected has happened, else 1

    testConfig = ConfigObj(args.filename)
    streams = testutils.create_cfg_files(testConfig)
    check_interval = int(testConfig['checkInterval'])
    test_length = int(testConfig['length'])
    fileDurationMinutes = int(testConfig['filedurationminutes']) if 'filedurationminutes' in testConfig else 60
    
    original_files = []  
    for s in streams:
        if os.path.exists(s[2]):
            for f in os.listdir(s[2]):
                original_files.append(os.path.join(s[2], f))

    process, thread = testutils.run_streamrecorder()
    time.sleep(2) # let dirs get created
    stime = time.time()
    
    # set-up database
    if os.path.isfile('test.db'):
        os.remove('test.db')
    conn = sqlite3.connect('test.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE Intervals
                (time, filename, size, rate)''')
    c.execute('''CREATE TABLE Files
                (file, creation_time, last_modified_time, start_size, end_size, avg_growth)''')

    print ('\n--Test starting--\n')

    check_command_thread = ThreadPool(processes=1)
    commands_result = check_command_thread.apply_async(testutils.check_command)    
    
    watchers = []
    for s in streams:
        watchers.append(DirectoryWatcher(s, stime, check_interval, test_length))
        
    while time.time() <= stime + test_length:
        time.sleep(check_interval)
        growing = False
        deletedFileInfo = []
        for w in watchers:
            if not w.check_status():
                exit_code = 1
                print ('ERROR: {} not growing when it should (time: {})'.format(
                    w.dirName, datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')))
            deletedFileInfo.append(w.get_deleted_file_info())
        avgSize = sum(s for _, s, _ in deletedFileInfo) / len(deletedFileInfo)
        for f, s, a in deletedFileInfo:
            if f != set():
                if s + 5 * a < avgSize:
                    exit_code = 1
                    print('Error deleted file(s) {} while other streams are more full'.format(f))
            
    process.terminate()
    etime = time.time() # end time
            
    for w in watchers:
        file_stats = w.get_statistics()
        for filename, stats in file_stats.items():
            if filename not in original_files:
                diff = 1
                diff = (datetime.datetime.strptime(stats[-1][0], '%Y/%m/%d %H:%M:%S') - datetime.datetime.strptime(stats[0][0], '%Y/%m/%d %H:%M:%S')).total_seconds()
                try:                    
                    growth = (stats[-1][1] - stats[0][1]) / diff
                except:
                    growth = 0
                values = (filename, stats[0][0], stats[-1][0], stats[0][1], stats[-1][1], growth) 
                c.execute('''INSERT INTO Files
                            VALUES (?,?,?,?,?,?)''', values)
                for s in stats:
                    values = (s[0], filename, s[1], s[1]-s[2])
                    c.execute('''INSERT INTO Intervals
                                VALUES (?,?,?,?)''', values)
    
    # get the commands called
    try:
        commands = commands_result.get()
    except:
        print ('ERROR: Commands not returned correctly')
        exit_code = 1
        
    c.execute('SELECT * FROM Files WHERE last_modified_time != creation_time')
    files = c.fetchall()
    
    files_created = defaultdict(list)
    
    for f in files:
        parts = f[0].split('/')
        files_created[parts[-2]].append(parts[-1])     
    
    video_prefix = gethostname() + '_'    
    for s in streams:
        videoDir = s[2]
        print ('\n\n--{}--'.format(s[0]))
        stream_files_created = files_created[s[0]]
        last_dir = videoDir.split('/')[-1:][0]
        for i in stream_files_created:
            print ('Created: {}'.format(i))
            if video_prefix + last_dir not in i:
                exit_code = 1
                print ('Error: {} not in name'.format(video_prefix + last_dir))
            else:
                print ('Does contain {}'.format(video_prefix + last_dir))
                
        print ('\nCreated {} files.'.format(len(stream_files_created)))
        if s[1].lower() == 'test' or s[1].lower() == 'always':
            expected_min_files, expected_max_files = testutils.expected_files_created(stime, time.time(), int(s[3]['filedurationminutes']), s[1])
            if len(stream_files_created) > expected_max_files:
                exit_code = 1
                print ('ERROR: Too many files created (expected {}-{})'.format(expected_min_files, expected_max_files))
            elif len(stream_files_created) < expected_min_files:
                exit_code = 1
                print ('Not enough files created (expected {}-{})'.format(expected_min_files, expected_max_files))
            else:
                print ('Correct number of files created (expected {}-{})'.format(expected_min_files, expected_max_files))
    
        # check correctness of the command
        if s[4] == None: # If stream type is ffmpeg
            try:
                s_cmds = commands[s[0]]
                all_commands_correct = True
                if s_cmds[s_cmds.index('-r')+1] != s[3]['framerate']:
                    print ('ERROR: FrameRate incorrectly entered')
                    all_commands_correct = False
                if s_cmds[s_cmds.index('-c:v')+1] != s[3]['codec']:
                    print ('ERROR: Codec incorrectly entered')
                    all_commands_correct = False
                if ('-rtsp_transport' not in s_cmds) and (s_cmds[s_cmds.index('-qscale:v') + 1] != s[3]['quality']):
                    print ('ERROR: Quality incorrectly entered, expected: {}, actual: {}.'.format(s[3]['Quality'], s_cmds[s_cmds.index('-qscale:v') + 1]))
                    all_commands_correct = False
                if all_commands_correct:
                    print ('Command was entered correctly')
                else:
                    exit_code = 1
            except Exception as e:
                print(e)
                exit_code = 1
                print ('ERROR: Something happened with checking commands')   
        else:
            pass
    # end for loop

    conn.commit()
    print ('\nStart Time: {}\nEnd Time: {}'.format(datetime.datetime.fromtimestamp(stime).strftime('%Y-%m-%d %H:%M:%S'), datetime.datetime.fromtimestamp(etime).strftime('%Y-%m-%d %H:%M:%S')))
    sys.exit(exit_code)