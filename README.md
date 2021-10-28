# streamrecorder
Streamrecorder records and stores output from multiple streams at the same time. The user can either specify a camera or a custom command for the stream. The 
camera recorders rely on FFMPEG to do most of the heavy lifting.

## Streamrecorder Features

### Nightly restarts
Streamrecorder will restart the cameras every night at midnight. This prevents various problems that can arise when the cameras are on for an extended 
period of time. Streamrecorder can either interact with the cameras through ONVIF or FTS. In order for ONVIF to work, ONVIF needs to be pulled from 
GitHub, and its directory must be specified in the configuration files. FTS requires no additional software to work. Optionally, this functionality 
can be turned off in the configuration files.

### Corrupted USB drive checking
If the streams fail to write many times in succession and USB storage is being used, streamrecorder will switch USB drives. This will ensure that if one 
of the USB drives is corrupted, streamrecorder will not attempt to use that USB drive indefinitely. It’s important to note that whether or not streamrecorder 
thinks that the streams are being recorded to a corrupted drive is based on the return code for ffmpeg. If ffmpeg returns a non-zero error code multiple times, 
Streamrecorder will assume it is because of a corrupted USB drive.

### Information reporting
Streamrecorder sends back various statistics related to how many files it has recorded, how much memory has been used, and information about how each individual 
stream is doing. How often the report gets sent back is specified in the configuration files. The receive.py script can be run on a remote server to receive the 
reports and save the information to a text file. 

### Voltage recording
Streamrecorder is able to the read the voltage from a USB voltmeter. The voltage will get sent back with the information described above. If no voltmeter is hooked 
up, the voltage will just be returned as null.

Note:The executable stop with the the message: "the user has insufficient permissions to access USB devices"
By default, Linux prevents write access to USB devices for non-root users. This is due to udev device manager.
The udev rules are stored in files placed in the /etc/udev/rules.d directory. The file name must matche the "##-ArbitraryName.rules" pattern.
When starting the system, udev will read in alphabetical order all files with the extension ".rules" in this directory, and apply the rules.

Allow all users to use Yoctopuce modules
The following rule allows all users to read and write to Yoctopuce USB devices. Access rights for all other devices are not changed.

# udev rules to allow write access to all users for Yoctopuce USB devices
SUBSYSTEM=="usb", ATTR{idVendor}=="24e0", MODE="0666"


## Configuring the program
The easiest way to configure streamrecorder is through the ```dvr-config.py``` script. Detailed documentation on its usage is provided along with it. To view the usage options for the script, enter the command ```dvr-config.py -h```, which will print information on the options the program supports. More information on what each of the options does can be seen with the command ```dvr-config.py -hh```. More information on the configuration files used can be read below.

## Configuration Files
 - streams.cfg:               File defining streams to record along with schedule and recording parameters
 - streamrecorder.cfg:       Main configuration file for defining general program settings.
 - camerainfo.cfg:           Configuration file defining stream info for different camera manufacturers
 - streamrecorder.conf:      Upstart job configuration for starting on boot
 - streamrecorder.service:   Systemd service configuration to define service and start on boot

## Program Files
 - streamrecorder.py:    Main program
 - stream.py:            Manages the streams
 - schedule.py:          Keeps track of when streams should record
 - dvrutils.py:          Contains various helper functions
 - sender.py:            Send information about the streams back to the lab
 - tracker.py            Gathers various information to send back to the lab
 - voltmeter.py          Manages a USB voltmeter

## Installation

### systemd
Copy systemd service definition to the service directory and enable it:
```
sudo cp /path/to/streamrecorder/streamrecorder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamrecorder.service
```

The program will now start on boot. You can use the following commands to control and inspect the service:
```
sudo systemctl start|stop|restart streamrecorder.service
sudo systemctl [-l] status streamrecorder.service
```

(Use `systemctl --help` or `man systemctl` for full systemd documentation)

### Ansible playbook
Before you run the playbook, make sure you have obtained the private key for the streamrecorder repository. Then in the ```/etc/ansible/hosts``` file, add the ip
addresses of the devices you want to install it on. Finally, enter the following command:
```
ansible-playbook setup_streamrecorder.yml --ask-pass --ask-become-pass
```
Then it will ask you for the ssh password and sudo password. Once those are entered it will run. For more information go to https://docs.ansible.com

###  Upstart (deprecated)
(**NOTE: For better or worse, Upstart has been left behind by the Linux community in favor of systemd,
a newer service daemon with a different configuration system. For ease of use when installing on
new systems, it is recommended that you use the systemd configuration described above.**)

Copy Upstart job configuration file to Upstart directory
```
sudo cp /path/to/streamrecorder/streamrecorder.conf /etc/init/
```

The program will now start on boot. You can start/stop/restart it manually by using the following commands:
```
sudo start streamrecorder
sudo stop streamrecorder
sudo restart streamrecorder
```
