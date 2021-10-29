import json
import pika
import threading
import time

class InformationSender(object):
    
    def __init__(self, smTracker, user, passwd, ip, sendIntervalMinutes, logger):
        self.smTracker = smTracker
        self.user = user
        self.passwd = passwd
        self.ip = ip
        self.thread = None
        self.sendIntervalSeconds = sendIntervalMinutes * 60
        self.logger = logger
        self.lastSend = time.time()
        self.reportFail = False
        
    def check_sender(self):
        if time.time() > self.lastSend + self.sendIntervalSeconds:
            # send using a thread, so that is done separtely from the program
            self.thread = threading.Thread(target=self.send_info)
            self.thread.daemon = True
            self.thread.start()
            self.lastSend = time.time()
        if self.reportFail:
            self.reportFail = False
            self.logger.warning('Failed to send stream information')
    
    def send_info(self): # TODO: what is virtual_host? Should it be read in as an argument?
        try:
            # open a connection to the message queue server
            creds = pika.PlainCredentials(self.user, self.passwd)
            params = pika.ConnectionParameters(self.ip, virtual_host='/username', credentials=creds)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            
            # declare a channel
            channel.queue_declare(queue='hello')
            
            # format the message and serialize it with JSON
            data = self.smTracker.get_stats()
            body = json.dumps(data)
    
            # send the message
            channel.basic_publish(exchange='',
                              routing_key='hello',
                              body=body)
            self.logger.info('Sent stream information')
            
            # close the connection
            connection.close()
        except:
            self.reportFail = True