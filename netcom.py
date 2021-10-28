#!/usr/bin/python

import SocketServer, socket
import threading, Queue
import hashlib, netaddr
import argparse

class Communicator:
    """The communication module of the server, handling receipt and transmission of data over the network with a SocketServer and verifying messages with an md5 hash."""
    # NOTE/TODO: This data is sent UNENCRYPTED over the network. To secure the communiation channel, use TLS/SSL (e.g. ssl or, probably, OpenSSL)
    def __init__(self, port=49450, dest='localhost'):
        self.port = port
        self.dest = dest
        self.rxMsgs = Queue.Queue()                     # messages that have been received by the server
        self.txMsgs = Queue.Queue()                     # messages that have been transmitted by the server
        self.authorizedHostNets = ['127.0.0.1/32',      # hosts that are authorized to communicate with this server (CIDR or glob notation)
                                   '192.168.1.0/24',
                                   '10.179.1.0/24']
        self.get_authorized_hosts_list()
        self.isListening = False
        #self.recipients = []                           # list of previous message recipients (as (host, port) tuples)
    
    def __del__(self):
        if self.isListening:
            self.stop_listening()
    
    def add_authorized_host(self,netstr):
        self.authorizedHostNets.append(netstr)
        self.get_authorized_hosts_list()
        
    def remove_authorized_host(self,netstr):
        while netstr in self.authorizedHostNets:
            self.authorizedHostNets.remove(netstr)
        self.get_authorized_hosts_list()
    
    def get_authorized_hosts_list(self):
        self.authorizedHosts = []
        for ahn in self.authorizedHostNets:
            netstr = netaddr.glob_to_cidrs(ahn)[0] if '*' in ahn else ahn
            self.authorizedHosts.append(netaddr.IPNetwork(netstr))
    
    def listen(self):
        """Starts a listener thread that reads and processes messages."""
        SocketServer.TCPServer.allow_reuse_address = True
        self.server = self.NetComTCPServer(('',self.port), self.TCPHandler)
        self.server.authorizedHosts = self.authorizedHosts
        self.server.rxMsgs = self.rxMsgs
        self.serverThread = threading.Thread(target=self.server.serve_forever)
        self.serverThread.start()
        self.isListening = True
        print "Listening on port {}...".format(self.port)
        
    def stop_listening(self):
        self.server.shutdown()
        self.server.server_close()
        self.isListening = False
        
    def print_messages_received(self):
        print "Messages received on port {}".format(self.port)
        print "=========================================="
        while True:
            try:
                data = self.rxMsgs.get_nowait()
                print data
            except Queue.Empty:
                # no data available, don't do anything
                pass
           
    def talk(self, msg, dest='', port=-1, printSuccess=False):
        """Send a message to another Communicator and verify transmission."""
        port = self.port if port == -1 else port        # use the same port unless the other host needs us to use a different one (why? do we need to do this?)
        dest = self.dest if dest == '' else dest
        self.lastRecipient = (dest, port)
        self.success = False
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.lastRecipient)
            self.sock.sendall(msg)
            self.response = self.sock.recv(1024)
            #print "Message  hash: {}".format(hashlib.md5(msg).hexdigest())
            #print "Response hash: {}".format(self.response)
            if self.response == hashlib.md5(msg).hexdigest():
                self.success = True
        except socket.error as sockErr:
            if sockErr.errno == 104:
                print "Error! Message refused by host {}! Make sure you are authorized!".format(dest)
        finally:
            self.sock.close()
            if self.success and printSuccess:
                print "Message successfully delivered!"
            elif printSuccess:
                print "Uh-oh...I couldn\'t deliver the message!"
        return self.success

    class NetComTCPServer(SocketServer.TCPServer):
        """Server class for the SocketServer (to add some verification, etc.).
        """
        def verify_request(self,request,client_address):
            for ahn in self.authorizedHosts:
                if client_address[0] in ahn:
                    return True
            print "Message received from unauthorized host {}!".format(client_address)
            return False

    class TCPHandler(SocketServer.BaseRequestHandler):
        """RequestHandler class for the SocketServer.
        """
        def handle(self):
            # reads data from the client and puts it in the Queue rxMsgs to be processed by the program
            self.data = self.request.recv(1024)                             # read data from client
            self.server.rxMsgs.put(self.data)                               # put the data in the queue for other methods to read it
            self.request.sendall(hashlib.md5(self.data).hexdigest())        # send back the md5 hash for verification
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='netcom.py', usage='%(prog)s [options] [message]', description='Program/module for insecure TCP communication over a network. (TLS Coming soon...).', epilog = 'When run as a script with no arguments, starts a server on the default port and listens for messages, printing them to the screen. When run with positional arguments, reads them as words of a message to send to msgDest.')
    parser.add_argument('-p', '--port', dest = 'port', type = int, default = 49450, help = 'TCP port to use, (default %(default)s).')
    parser.add_argument('-d', '--dest', '--destination', dest = 'msgDest', default = 'localhost', help = 'The hostname/IP of the message destination (default %(default)s).')
    parser.add_argument('message', nargs=argparse.REMAINDER, help = 'The message to send to msgDest.')
    args = parser.parse_args()
    
    if len(args.message) > 0:
        msg = " ".join(args.message)
        com = Communicator(args.port)
        com.talk(msg,dest=args.msgDest)
    else:
        # if in server mode, start the server and listen, stopping if they press Ctrl+C
        print "Starting server..."
        com = Communicator(args.port)
        try:
            com.listen()
            com.print_messages_received()
        except KeyboardInterrupt:
            print "Stopping server..."
            com.stop_listening()
            
        