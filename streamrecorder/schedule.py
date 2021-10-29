import time
import sys
from math import ceil

sys.path.append('..')

import streamrecorder.dvrutils as dvrutils

DAYS_OF_WEEK = [time.strftime('%A', time.strptime(str(i), '%w')) for i in range(0,7)]

def matchday(dayStr):
    # try to match well-formatted names (anything that uses non-ambiguous abbreviations)
    for d in DAYS_OF_WEEK:
        minLen = min(len(d), len(dayStr))
        if d[0:minLen].lower() == dayStr[0:minLen].lower():
            return d
    
    # if nothing was found, try to match anything (NOTE: May cause interesting results...)
    day, maxlcss = '', ''
    for d in DAYS_OF_WEEK:
        lcss = dvrutils.longest_common_substring(d.lower(), dayStr.lower())
        if len(lcss) > len(maxlcss):
            maxlcss = lcss
            day = d
    return day

class RecordingDay:
    """A class for holding the recording times for a day."""
    def __init__(self, dayStr, fileDuration):
        self.dayStr = dayStr
        self.dayOfWeekNum = DAYS_OF_WEEK.index(dayStr)
        self.fileDuration = fileDuration
        self.recordingIntervals = []                    # list of (startSecond,endSecond) tuples

    def __eq__(self, rhs):
        return self.is_equal(rhs)
    
    def __ne__(self, rhs):
        return not self.is_equal(rhs)
        
    def add_recording_interval(self, timeStr):
        # timeStr will be HHMM-HHMM, e.g. 0900-2100
        try:
            start, end = timeStr.strip().split('-')
            startHour, startMin = int(start[0:2]), int(start[2:])
            endHour, endMin = int(end[0:2]), int(end[2:])
            startSec = startHour*3600 + startMin*60
            endSec = endHour*3600 + endMin*60
            self.recordingIntervals.append((startSec,endSec))
        except ValueError:
            pass
        
    def check_day_schedule(self, t):
        for start, end in self.recordingIntervals:
            if t >= start and t < end:
                return True
        return False
        
    def get_interval_end(self, time): # time between 0 and 86400
    # accounts for overlapping intervals to find the end of the recording time
        if 0 <= time <= 86400:
            for i in self.recordingIntervals:
                if i[0] <= time < i[1]:
                    return self.get_interval_end(i[1])
        return time
    
    def is_equal(self, rhs):
        # NOTE: two days record at the same time, depending on how intervals are broken up
        # Ex: [(0, 86400)] != [(0, 36000), (36000, 86400)] even though they record at the same time
        if self.dayStr != rhs.dayStr:
            return False
        if len(self.recordingIntervals) != len(rhs.recordingIntervals):
            return False
        # nest loops so the order the intervals where added does not matter
        for left in self.recordingIntervals:
            for right in rhs.recordingIntervals:
                if left == right:
                    break
            else:
                return False
            # END inner for loop
        # END outer loop
        return True
        

class RecordingSchedule:
    """A class for containing a recording schedule."""
    def __init__(self, scheduleString='', fileDurationMinutes=60, scheduleFilename='', dataType='Video'):
        self.dataType = dataType
        self.recordingDays = {}
        if 60%int(fileDurationMinutes) != 0:
            self.fileDurationMinutes = 60
        else:
            self.fileDurationMinutes = int(fileDurationMinutes)
        self.fileDuration = int(self.fileDurationMinutes) * 60
        self.haveSchedule = False
        if scheduleFilename != '':
            self.scheduleFilename = scheduleFilename
            self.read_schedule_file()
        elif scheduleString != '':
            self.read_schedule_string(scheduleString)
     
    def __eq__(self, rhs):
        return self.is_equal(rhs)

    def __ne__(self, rhs):
        return not self.is_equal(rhs)
        
    def clear_schedule(self):
        self.recordingDays = {}
        self.haveSchedule = False
        
    def read_schedule_string(self, scheduleString):
        self.clear_schedule()
        scheduleString = scheduleString.strip()
        if 'always' in scheduleString:
            for day in DAYS_OF_WEEK:
                self.recordingDays[day] = RecordingDay(day, self.fileDuration)
                self.recordingDays[day].add_recording_interval('0000-2400')
        else:
            for s in scheduleString.split(';'):
                dayStr, timeStr = '', ''
                if ':' in s:
                    dayStr, timeStr = s.split(':')
                else:
                    # otherwise figure out if they gave us a day range or time range
                    snp = s.strip().strip('()')
                    if '-' in snp:                    # range
                        sps = snp.split('-')
                        if sps[0].isalpha():        # day range
                            dayStr = snp
                        elif sps[0].isdigit():        # time range
                            timeStr = snp
                    else:                  # list or single item (days only)
                        dayStr = s
                    
                if dayStr != '':            # if they gave us a day string
                    if timeStr == '':       # day with no time defaults to all day
                        timeStr = '0000-2400'
                    if '-' in dayStr:                   # day range
                        startDay, endDay = dayStr.split('-')
                        startDay, endDay = time.strptime(matchday(startDay.strip()), '%A'), time.strptime(matchday(endDay.strip()), '%A')    # returns full day names (%A)
                        dayList = [DAYS_OF_WEEK[d] for d in range((startDay.tm_wday+1)%7, ((endDay.tm_wday+1)%7)+1)]
                    elif ',' in dayStr:                 # day list
                        dayList = [matchday(d.strip()) for d in dayStr.split(',')]
                    else:
                        dayList = [matchday(dayStr.strip())]
                else:       # if they didn't give us a day string, it's every day
                    dayList = DAYS_OF_WEEK
                    
                if timeStr != '':           # if we have a time string (with one or more time intervals), go through all of them
                    for day in dayList:
                        if day not in self.recordingDays:
                            self.recordingDays[day] = RecordingDay(day, self.fileDuration)
                        for ts in timeStr.strip().strip('()').split(','):
                            self.recordingDays[day].add_recording_interval(ts)
        self.haveSchedule = True
        
    def read_schedule_file(self):
        # reads the recording schedule to determine what times of what days the program should be recording
        if self.scheduleFilename != '':
            with open(self.scheduleFilename, 'r') as scheduleFile:
                readMode = 0              # variable indicating whether the actual schedule has been reached (instead of just the comments)
                fileLines = scheduleFile.readlines()
            for line in fileLines:
                if readMode == 0 and '{} Recording Schedule'.format(self.dataType) in line:
                    readMode = 1
                if readMode == 1 and 'Day' in line:
                    readMode = 2
                elif readMode == 2:
                    splitLine = line.split(',')
                
                    # extract information from line
                    dayStr = splitLine[0]
                    startTimeStr = splitLine[1]
                    endTimeStr = splitLine[2]
                    
                    if ':' in startTimeStr:
                        h,m = startTimeStr.split(':')
                        startTimeStr = h+m
                    if ':' in endTimeStr:
                        h,m = endTimeStr.split(':')
                        endTimeStr = h+m
                    
                    dayOfWeek = time.strptime(dayStr, '%A').tm_wday     # convert day string into day of week number
                    self.recordingDays.update({dayOfWeek: RecordingDay(dayOfWeek, dayStr, startTimeStr, endTimeStr, self.fileDuration)})
            self.haveSchedule = True
    
    def print_recording_schedule(self, logger=None):
        # prints the recording schedule after it is read for logging purposes       
        def log_it(msg, logger=None):
            if logger is None:
                print (msg)
            else:
                logger.info(msg)
        
        if self.haveSchedule:
            log_it("\n---Recording Schedule---", logger)
            for day in list(self.recordingDays.values()):
                log_it("Recording on {}s in {} minute blocks in the following intervals:".format(day.dayStr, day.fileDuration/60), logger)
                for start, end in day.recordingIntervals:
                    log_it("  {} to {}".format(dvrutils.format_time(start, withSeconds=False),dvrutils.format_time(end, withSeconds=False)), logger)
            log_it("---End Recording Schedule---\n", logger)
    
    def check_recording_schedule(self, atTime=None):
        # checks whether the program should be recording, now or at atTime
        recording = False
        if self.haveSchedule:
            atTime = time.time() if atTime is None else atTime
            currTime = time.localtime(atTime)
            day = DAYS_OF_WEEK[(currTime.tm_wday + 1) % 7]
            currSec = currTime.tm_hour*3600 + currTime.tm_min*60
            if day in self.recordingDays:
                recording = self.recordingDays[day].check_day_schedule(currSec)
        return recording

    def get_interval_endtime(self, startTime):
        # Gets the end of the recording interval given a start time
        currTime = time.localtime(startTime)
        seconds = currTime.tm_hour * 3600 + currTime.tm_min * 60 + currTime.tm_sec
        try:
            day = self.recordingDays[DAYS_OF_WEEK[(currTime.tm_wday + 1) % 7]]
            return day.get_interval_end(seconds)
        except:
            return 0
    
    # TODO: Fix bug in this function that causes negative times to be output (when file intervals are 10 minutes, possibly others)
    def get_recording_duration(self, atTime=None):
        # retrieves the length of the next file to be recorded (in case it was brought up in the middle of an interval)
        recordSecs = 0        
        if self.check_recording_schedule(atTime) is True:
            atTime = time.time() if atTime is None else atTime
            currTime = time.localtime(atTime)
            currHour = currTime.tm_hour
            currMin = currTime.tm_min
            currSec = currTime.tm_sec

            nextStartMin = self.get_start_minute(currMin)
            recordSecs = (nextStartMin - currMin)*60
            if currSec != 0:
                recordSecs -= currSec               # subtract time that has passed since the start of the minute
            
            # in case the schedule end time isn't divisable by fileDurationMinutes
            nextEnd = self.get_interval_endtime(atTime) - currHour * 3600 - currMin*60 - currSec
            recordSecs = min(recordSecs, nextEnd)            
            
        return recordSecs
    
    def get_start_minute(self, currMin):
        # round up to the next interval start
        if (currMin % self.fileDurationMinutes) == 0:
            startMin = currMin + self.fileDurationMinutes
        else:
            startMin = int(ceil(currMin/float(self.fileDurationMinutes))*self.fileDurationMinutes)
        if startMin >= 60:
            startMin = 60       # set to 60 if it's greater than 60
        return startMin
    
    def is_equal(self, rhs):
        if type(rhs) == str: # so you can check with just a string
            rhs = RecordingSchedule(rhs)
        if self.recordingDays.keys() != rhs.recordingDays.keys():
            return False
        for day in self.recordingDays.keys():
            if self.recordingDays[day] != rhs.recordingDays[day]:
                return False
        else:
            return True