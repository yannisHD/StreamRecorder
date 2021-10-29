# This is used to test the command stream
import argparse
import os
import time

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='filename', default='test.cfg')
    args = parser.parse_args()
    
    filename = args.filename
    
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            f.write('Hello World\n')

    
    while True:
        with open(filename, 'a') as f:
            f.write('Hello, World\n')
        time.sleep(1)