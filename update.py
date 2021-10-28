#!/usr/bin/python

import os, time, signal, argparse
import subprocess32 as subprocess

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__), usage='%(prog)s [options]', description='Update a streamrecorder installation in an active Git repository from behind an over-zealous firewall that prevents communicating with the repo. Can also update the OS with apt-get.')
    # Examples: 
    # Positional argument: parser.add_argument('filename', help = 'Name/path of the script file you want to create.')
    #parser.add_argument('-s','--sshuttle', dest='sshuttlePath', default = os.path.join(os.environ['HOME'],'sshuttle/sshuttle'), help = 'Path to sshuttle executable, used for tunnelling out (default %(default)s).',)
    parser.add_argument('-p','--proxy', dest='proxyHost', default = 'laozi', help = 'Host to use for SSH proxy tunnel to get around the firewall (default %(default)s).')
    parser.add_argument('-n','--maxtries', dest='maxTries', type = int, default = 5, help = 'Maximum number of times to try to connect to proxyHost (default %(default)s).')
    parser.add_argument('-sr','--streamrecorder', dest='streamrecorderDir', default = os.path.join(os.environ['HOME'],'streamrecorder'), help = 'Directory containing streamrecorder installation (default %(default)s).')
    parser.add_argument('-u','--upgrade-dist', dest='upgradeDist', action = 'store_true', help = 'Update the operating system with apt-get.')
    parser.add_argument('-U','--only-upgrade-dist', dest='onlyUpgradeDist', action = 'store_true', help = 'Only update the operating system with apt-get, do not upgrade streamrecorder.')
    parser.add_argument('-c','--command', dest='command', help = 'Command or script to execute, to run instead of updating streamrecorder (enclose this in quotes!).')
    args = parser.parse_args()
    
    print "Starting sshuttle to {}".format(args.proxyHost)
    proxyCmd = ['sudo', 'sshuttle','-r',args.proxyHost,'0/0'] # adding sshuttle to the nopasswd list for username lets you do this without entering password
    p = None
    try:
        p = subprocess.Popen(proxyCmd)
        for i in range(0,args.maxTries):
            time.sleep(5)
            pstat = p.poll()
            if pstat is not None:
                print "sshuttle stopped! On attempt {} of {}!".format(i,args.maxTries)
                p.subprocess.Popen(proxyCmd)
            else:
                break
            
        # upgrade OS
        if args.upgradeDist or args.onlyUpgradeDist:
            print "Upgrading OS..."
            subprocess.call(['sudo','apt-get','update'])
            subprocess.call(['sudo','apt-get','-y','upgrade'])
            subprocess.call(['sudo','apt-get','-y','dist-upgrade'])
        
        # upgrade streamrecorder or run command
        if not args.onlyUpgradeDist:
            if args.command is not None:
                print "Executing command: \"{}\"".format(args.command)
                os.system(args.command)
            else:
                # now that sshuttle is running, update streamrecorder with git (NOTE: Assumes the repository exists already!)
                os.chdir(args.streamrecorderDir)
                updateCmd = ['sudo','-u','username','git','pull','origin','master']
                subprocess.call(updateCmd)
    finally:
        # make sure to kill the sshuttle process if it is left open, otherwise it will lock us out of the machine
        if p is not None:
            print "Terminating sshuttle proxy..."
            p.send_signal(signal.SIGINT)
            p.wait()
            print "sshuttle terminated successfully."

