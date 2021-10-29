import pytest
import sys
import time

from unittest import mock

sys.path.append('..')
from streamrecorder import sender

@pytest.fixture
def logger():
    loggerMock = mock.Mock()
    return loggerMock

def test_cotr():
    infoSender = sender.InformationSender('dummy', 'user', 'passwd', '240.0.0.0',
                                          5, 'dummy2')
    assert infoSender.smTracker == 'dummy'
    assert infoSender.user == 'user'
    assert infoSender.passwd == 'passwd'
    assert infoSender.ip == '240.0.0.0'
    assert infoSender.thread == None
    assert infoSender.sendIntervalSeconds == 300
    assert infoSender.logger == 'dummy2'
    assert time.time() - 1 < infoSender.lastSend < time.time() + 1
    assert infoSender.reportFail == False
    

def test_send_info():
    smTrackerMock = mock.Mock()
    smTrackerMock.get_stats.return_value = {'time' : '20180813'}
    infoSender = sender.InformationSender(smTrackerMock, 'username', '***REMOVED***', 
                                          '10.179.1.2', 5, logger())
    infoSender.send_info()
    smTrackerMock.get_stats.assert_called_with()