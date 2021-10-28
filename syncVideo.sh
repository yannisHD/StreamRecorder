#!/bin/bash

# Simple script for a DVR to push (sync) video to a remote server


# Configuration constants
VIDEO_DIR=/mnt/video
SERVER_MOUNT_DIR=/mnt/MTO_Research_Student
SERVER_DIR=/mnt/MTO_Research_Student/Beholder_Video/from_field/$(hostname)

# First make sure the remote directory is mounted
if ! mountpoint $SERVER_MOUNT_DIR; then
    echo "Mounting remote filesystem at $SERVER_MOUNT_DIR"
    mount $SERVER_MOUNT_DIR
fi

# only do something if mounting worked
ret=1
if mountpoint $SERVER_MOUNT_DIR; then
    echo "Pushing video from $VIDEO_DIR to $SERVER_DIR ..."
    # make the directory
    mkdir -p $SERVER_DIR
    
    # now run rsync to copy the video
    # NOTE the slash at the end of VIDEO_DIR - this will dump the contents of
    # VIDEO_DIR into SERVER_DIR
    rsync -av --progress $VIDEO_DIR/ $SERVER_DIR/; ret=$?
fi

exit $ret
