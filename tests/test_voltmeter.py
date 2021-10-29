import pytest
import sys

from unittest import mock

sys.path.append('..')

from streamrecorder import voltmeter

@pytest.fixture
def logger():
    loggerMock = mock.Mock()
    return loggerMock

@mock.patch('yoctopuce.yocto_api.YAPI.RegisterHub')
@mock.patch('yoctopuce.yocto_api.YRefParam')
@mock.patch('yoctopuce.yocto_voltage.YVoltage')
def test_ctor(yVoltageMock, yRefMock, regHubMock, logger):
    regHubMock.return_value = 0
    yRefMock.return_value = 'errormsg'
    sensorMock = mock.Mock()
    moduleMock = mock.Mock()
    sensorDCMock = mock.Mock()
    sensorDCMock.isOnline.return_value = True
    yVoltageMock.FindVoltage.return_value = sensorDCMock
    yVoltageMock.FirstVoltage.return_value = sensorMock
    sensorMock.get_module.return_value = moduleMock
    moduleMock.get_serialNumber.return_value = 'serialNum'
    
    meter1 = voltmeter.Voltmeter(logger)
    assert meter1.isWorking == True
    assert meter1.sensor == sensorMock
    assert meter1.serialNumber == 'serialNum'
    assert meter1.sensorDC == sensorDCMock
    regHubMock.assert_called_with('usb', 'errormsg')
    yVoltageMock.FindVoltage.assert_called_with('serialNum.voltage1')
    
    regHubMock.return_value = 1
    meter2 = voltmeter.Voltmeter(logger)
    assert meter2.isWorking == False
    
def test_get_voltage(logger):
    meter = voltmeter.Voltmeter(logger)
    sensorDCMock = mock.Mock()
    sensorDCMock.get_currentValue.return_value = 12.3
    meter.sensorDC = sensorDCMock
    
    meter.isWorking = True
    assert meter.get_voltage() == 12.3
    
    meter.isWorking = False
    assert meter.get_voltage() == None