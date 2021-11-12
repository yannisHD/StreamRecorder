#!/bin/bash

export PYTHONPATH=$HOME/python-packages:$PYTHONPATH

STREAMRECORDER_PATH=$HOME/StreamRecorder

cd $STREAMRECORDER_PATH
$STREAMRECORDER_PATH/streamrecorder.py

