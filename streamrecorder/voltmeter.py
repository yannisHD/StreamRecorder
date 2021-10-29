class Voltmeter(object):
    
    def __init__(self, logger):
        self.logger = logger
        self.isWorking = False
        try:
            from yoctopuce.yocto_api import YAPI, YRefParam
            from yoctopuce.yocto_voltage import YVoltage
            errormsg = YRefParam()
            if YAPI.RegisterHub('usb', errormsg) != YAPI.SUCCESS:
                raise Exception('init error {}'.format(errormsg.value))
            self.sensor = YVoltage.FirstVoltage()
            self.serialNumber = self.sensor.get_module().get_serialNumber()
            self.sensorDC = YVoltage.FindVoltage(self.serialNumber + '.voltage1')
            if not self.sensorDC.isOnline():
                raise Exception('Something is wrong with module!')
            self.isWorking = True
            
        except Exception as e:
            self.logger.warning('Failed to setup voltometer!')
            self.logger.warning('Error message: {}'.format(e))
            
    def get_voltage(self):
        if self.isWorking:
            try:
                return self.sensorDC.get_currentValue()
            except:
                return None
        else:
            return None
