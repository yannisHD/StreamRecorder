import datetime
import pytest
import time
import sys

sys.path.append('..')

import streamrecorder.schedule as schedule

def test_matchday():
    assert schedule.matchday('MoNdaY') == 'Monday'
    assert schedule.matchday('tuesday') == 'Tuesday'
    assert schedule.matchday('Wed') == 'Wednesday'


#==============================================================================
# RecordingDay tests
#==============================================================================


@pytest.fixture
def create_day():
    return schedule.RecordingDay('Sunday', 45)

def test_RecordingDay_ctor():
    day = create_day()
    assert day.dayStr == 'Sunday'
    assert day.dayOfWeekNum == 0
    assert day.fileDuration == 45
    assert day.recordingIntervals == []
    
    
def test_add_recording_interval():
    day = create_day()
    day.add_recording_interval('0651-1330')
    day.add_recording_interval('1400-1600')
    assert day.recordingIntervals == [(24660, 48600), (50400, 57600)]
    
    
def test_check_day_schedule():
    day = create_day()
    day.add_recording_interval('0651-1330')
    day.add_recording_interval('1400-1600')    
    assert day.check_day_schedule(50000) == False
    assert day.check_day_schedule(30000) == True

def test_get_interval_end():
    day = create_day()
    assert day.get_interval_end(0) == 0
    day.recordingIntervals = [(0,10000), (20000, 30000)]
    assert day.get_interval_end(0) == 10000
    assert day.get_interval_end(15000) == 15000
    assert day.get_interval_end(30000) == 30000
    assert day.get_interval_end(40000) == 40000
    day.recordingIntervals = [(0,10000), (5000, 15000)]
    assert day.get_interval_end(7000) == 15000
    day.recordingIntervals = [(5000, 15000), (0, 10000)]
    assert day.get_interval_end(7000) == 15000
    day.recordingIntervals = [(10000, 20000), (0, 15000), (17500, 22500), (25000, 35000)]
    assert day.get_interval_end(0) == 22500
    
def test_day_is_equal():
    day = schedule.RecordingDay('Sunday', 60)
    day.add_recording_interval('1200-1300')
    day2 = schedule.RecordingDay('Sunday', 60)
    day2.add_recording_interval('1200-1300')
    assert day.is_equal(day2)
    day2.dayStr = 'Wednesday'
    assert not day.is_equal(day2)
    
    day = schedule.RecordingDay('Monday', 60)
    day.add_recording_interval('0900-1000')
    day2 = schedule.RecordingDay('Monday', 60)
    day2.add_recording_interval('0800-0900')
    assert not day.is_equal(day2)
    day2.add_recording_interval('0900-1000')
    assert not day.is_equal(day2)
    day.add_recording_interval('0800-0900')
    print ('intervals {} and {}'.format(day.recordingIntervals, day2.recordingIntervals))
    assert day.is_equal(day2)

def test_day__eq__():
    day = schedule.RecordingDay('Sunday', 60)
    day.add_recording_interval('1200-1300')
    day2 = schedule.RecordingDay('Sunday', 60)
    day2.add_recording_interval('1200-1300')
    assert day == day2
    day2.dayStr = 'Wednesday'
    assert not (day == day2)
    
    day = schedule.RecordingDay('Monday', 60)
    day.add_recording_interval('0900-1000')
    day2 = schedule.RecordingDay('Monday', 60)
    day2.add_recording_interval('0800-0900')
    assert not (day == day2)
    day2.add_recording_interval('0900-1000')
    assert not (day == day2)
    day.add_recording_interval('0800-0900')
    assert day == day2
    
def test_day__ne__():
    day = schedule.RecordingDay('Sunday', 60)
    day.add_recording_interval('1200-1300')
    day2 = schedule.RecordingDay('Sunday', 60)
    day2.add_recording_interval('1200-1300')
    assert not (day != day2)
    day2.dayStr = 'Wednesday'
    assert day != day2
    
    day = schedule.RecordingDay('Monday', 60)
    day.add_recording_interval('0900-1000')
    day2 = schedule.RecordingDay('Monday', 60)
    day2.add_recording_interval('0800-0900')
    assert day != day2
    day2.add_recording_interval('0900-1000')
    assert day != day2
    day.add_recording_interval('0800-0900')
    assert not (day != day2)
    
#==============================================================================
# RecordingSchedule tests
#==============================================================================

@pytest.fixture
def create_default_schedule():
    return schedule.RecordingSchedule()
    
@pytest.fixture
def create_schedule_with_string():
    return schedule.RecordingSchedule('Monday:0913-1200;1300-1400', 6)


def test_RecordingSchedule_ctor():
    my_schedule = schedule.RecordingSchedule()
    assert my_schedule.dataType == 'Video'
    assert my_schedule.recordingDays == {}
    assert my_schedule.fileDurationMinutes == 60
    assert my_schedule.fileDuration == 3600
    assert my_schedule.haveSchedule == False
    assert hasattr(my_schedule, 'scheduleFilename') == False
    assert hasattr(my_schedule, 'scheduleFilename') == False
    
    my_schedule = create_schedule_with_string()
    assert my_schedule.fileDurationMinutes == 6
    assert my_schedule.recordingDays['Sunday'].recordingIntervals == [(46800, 50400)]
  
    
def test_read_schedule_string():
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('always')
    days = [time.strftime('%A', time.strptime(str(i), '%w')) for i in range(0,7)]    
    for d in days:
        assert my_schedule.recordingDays[d].recordingIntervals == [(0, 86400)]
    assert my_schedule.haveSchedule == True
    
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('Monday:0913-1200;1300-1400')
    assert my_schedule.recordingDays['Monday'].recordingIntervals == [(33180, 43200), (46800, 50400)]
    assert my_schedule.recordingDays['Friday'].recordingIntervals == [(46800, 50400)]
    
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('Mon-Thu:0000-1000;Mon,Fri:1100-2000')
    print(my_schedule.recordingDays)
    assert 'Sunday' not in my_schedule.recordingDays
    assert 'Saturday' not in my_schedule.recordingDays
    assert my_schedule.recordingDays['Monday'].recordingIntervals == [(0, 36000), (39600, 72000)]
    assert my_schedule.recordingDays['Tuesday'].recordingIntervals == [(0, 36000)]
    assert my_schedule.recordingDays['Wednesday'].recordingIntervals == [(0, 36000)]
    assert my_schedule.recordingDays['Thursday'].recordingIntervals == [(0, 36000)]
    assert my_schedule.recordingDays['Friday'].recordingIntervals == [(39600, 72000)]
    
    my_schedule.read_schedule_string('Mon,Thu')
    assert my_schedule.recordingDays['Monday'].recordingIntervals == [(0, 86400)]
    assert my_schedule.recordingDays['Thursday'].recordingIntervals == [(0, 86400)]
    for d in ['Sunday', 'Tuesday', 'Wednesday', 'Friday', 'Saturday']:
        assert d not in my_schedule.recordingDays 
        
    
def read_schedule_file():
    my_schedule = create_default_schedule()
    my_schedule.scheduleFilename = 'testSchedule.txt'
    f = open('testSchedule.txt', 'w')
    f.write('Monday:0913-1200;1300-1400')
    my_schedule.read_schedule_file()
    assert my_schedule.recordingDays['Monday'].recordingIntervals == [(33180, 43200), (46800, 50400)]
    assert my_schedule.recordingDays['Friday'].recordingIntervals == [(46800, 50400)]    

def test_schedule_is_equal():
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('Mon-Wed:1000-1500')
    assert my_schedule.is_equal('Mon-Wed:1000-1500')
    assert my_schedule.is_equal(schedule.RecordingSchedule('Mon-Wed:1000-1500'))
    assert not my_schedule.is_equal('1000-1500')
    assert not my_schedule.is_equal(schedule.RecordingSchedule('Mon,Wed:1000-1500'))
    my_schedule.read_schedule_string('always')
    assert my_schedule.is_equal(schedule.RecordingSchedule('always'))
    assert my_schedule.is_equal(schedule.RecordingSchedule('0000-2400'))
    assert my_schedule.is_equal(schedule.RecordingSchedule('Sun-Sat:0000-2400'))
    assert my_schedule.is_equal(schedule.RecordingSchedule('Sun,Wed,Mon,Thu,Tue,Fri,Sat:0000-2400'))
        
def test_clear_schedule():
    my_schedule = create_schedule_with_string()
    my_schedule.clear_schedule()
    assert my_schedule.recordingDays == {}
    assert my_schedule.haveSchedule == False

def test_check_recording_schedule():
    my_schedule = create_default_schedule()
    assert my_schedule.check_recording_schedule() == False

    my_schedule = schedule.RecordingSchedule('always', 6)
    assert my_schedule.check_recording_schedule(100) == True 


def test_get_start_minute():
    my_schedule = create_schedule_with_string()
    assert my_schedule.get_start_minute(45) == 48
    assert my_schedule.get_start_minute(0) == 6
    assert my_schedule.get_start_minute(90) == 60

def test_get_recording_duration():
    midnight = (datetime.datetime(2018, 1, 1, 0, 0, 0) - datetime.datetime(1970,1,1)).total_seconds()
    midnight += time.mktime(time.gmtime()) - time.mktime(time.localtime())
    my_schedule = create_default_schedule()
    assert my_schedule.get_recording_duration() == 0
    
    my_schedule = schedule.RecordingSchedule('always', 6)
    assert my_schedule.get_recording_duration(240) == 120
    assert my_schedule.get_recording_duration(0) == 360
    
    my_schedule = schedule.RecordingSchedule('0000-0100', 60)
    assert my_schedule.get_recording_duration(midnight) == 3600
    my_schedule = schedule.RecordingSchedule('0000-0012', 60)
    assert my_schedule.get_recording_duration(midnight) == 720
    
def test_get_interval_endtime():
    midnight = (datetime.datetime(2018, 1, 1, 0, 0, 0) - datetime.datetime(1970,1,1)).total_seconds()
    midnight += time.mktime(time.gmtime()) - time.mktime(time.localtime())
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('0000-1000;0900-1100')
    assert my_schedule.get_interval_endtime(midnight) == 39600
    my_schedule.clear_schedule()
    my_schedule.read_schedule_string('0000-0012')
    assert my_schedule.get_interval_endtime(midnight) == 720
    
def test_schedule__eq__():
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('Mon-Wed:1000-1500')
    assert my_schedule == 'Mon-Wed:1000-1500'
    assert my_schedule == schedule.RecordingSchedule('Mon-Wed:1000-1500')
    assert not (my_schedule == schedule.RecordingSchedule('Mon,Wed:1000-1500'))
    assert not (my_schedule == '1000-1500')
    my_schedule.read_schedule_string('always')
    assert my_schedule == schedule.RecordingSchedule('always')
    assert my_schedule == schedule.RecordingSchedule('0000-2400')
    assert my_schedule == schedule.RecordingSchedule('Sun-Sat:0000-2400')
    assert my_schedule == schedule.RecordingSchedule('Sun,Wed,Mon,Thu,Tue,Fri,Sat:0000-2400') # order should not matter
    
def test_schedule__ne__():
    my_schedule = create_default_schedule()
    my_schedule.read_schedule_string('Mon-Wed:1000-1500')
    assert not (my_schedule != 'Mon-Wed:1000-1500')
    assert not (my_schedule != schedule.RecordingSchedule('Mon-Wed:1000-1500'))
    assert my_schedule != schedule.RecordingSchedule('Mon,Wed:1000-1500')
    assert my_schedule != '1000-1500'
    my_schedule.read_schedule_string('always')
    assert not (my_schedule != schedule.RecordingSchedule('0000-2400'))  