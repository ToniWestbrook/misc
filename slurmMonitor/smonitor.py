#! /usr/bin/env python3

# Copyright 2017, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

import array
import fcntl
import argparse
import subprocess
import sys
import shutil
import os
import pty
import tty
import termios
from threading import Thread

HOME_STRING = "\x1B[H"
CURSOROFF_STRING = "\x1B[?25l"
CURSORON_STRING = "\x1B[?25h"

def debugEsc(passChunk):
    for c in passChunk: 
        if ord(c) == 27: print()
        if ord(c) > 32: renderchar = c
        else: renderchar = ord(c)
        print("{0} ".format(renderchar), end='')

def parseNodes(passRaw):
    retNodes = list()

    # Check for single vs multinode format
    if not '[' in passRaw:
        retNodes.append(passRaw)
    else:
        nodeParts = passRaw.strip(']').split('[') 
        nodeBase = nodeParts[0]
        nodeGroups = nodeParts[1].split(',')

        for group in nodeGroups:
            if not '-' in group:
                retNodes.append("{0}{1}".format(nodeBase, group))
            else:
                nodeRange = group.split('-')
                for idx in range(int(nodeRange[0]), int(nodeRange[1]) + 1):
                    retNodes.append("{0}{1}".format(nodeBase, idx))

    return retNodes
        
def getSlurmInfo(passJob):
    retInfo = dict()

    # Obtain Slurm info
    command = "squeue -a -o %N\t%P\t%M\t%T -h -j {0}".format(passJob).split(' ')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    out, err = process.communicate()

    # Check for invalid IDs or other errors
    if err: return None

    # Parse values
    fields = out.decode('utf-8').rstrip().split("\t")
    nodes = parseNodes(fields[0])
  
    retInfo['id'] = passJob
    retInfo['nodes'] = nodes
    retInfo['partition'] = fields[1]
    retInfo['time'] = fields[2]
    retInfo['status'] = fields[3]

    return retInfo

def getStatusBar(passJob, passMonitor):
    # Obtain latest info
    slurmInfo = getSlurmInfo(passJob)
    slurmInfo['monitor'] = slurmInfo['nodes'][passMonitor]

    columns, rows = shutil.get_terminal_size()
    statusText = "Job: {id}  Status: {status}  Partition: {partition}  Time: {time}  Monitor: {monitor}".format(**slurmInfo)
    statusText += (' ' * (columns - len(statusText)))

    return statusText

def renderTop(passScreen, passJob, passNode):
    # Break screen into lines
    lines = passScreen.split("\n")

    # Render all but last line
    sys.stdout.write(HOME_STRING)
    sys.stdout.write(CURSOROFF_STRING)
    for line in lines[:-1]: sys.stdout.write("{0}\r\n".format(line))

    # Render Slurm status bar
    statusText = getStatusBar(passJob, passNode)
    sys.stdout.write("\x1B[44;37m{0}\x1B[0m".format(statusText))
    sys.stdout.flush()

def processTop(passSlurmInfo, passNode, passPty):
    # Start top process
    command = "ssh {0} -t top".format(passSlurmInfo['nodes'][passNode]).split(' ')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=passPty)

    # Change pty size to match terminal (
    sizeBuffer = array.array('h', [0, 0, 0, 0])
    fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, sizeBuffer, True)
    fcntl.ioctl(passPty, termios.TIOCSWINSZ, sizeBuffer)

    buffer = ''
    bufSize = 2
    while process.poll() is None:
        out = process.stdout.read(1)
        buffer += out.decode('utf-8')

        # Look for start of new screen
        bufParts = buffer.split(HOME_STRING)
        if len(bufParts) > bufSize:
            if passNode == main.monitor:
                renderTop(bufParts[bufSize - 1], passSlurmInfo['id'], passNode)
            buffer = ''.join(bufParts[bufSize:])
            if bufSize == 2: bufSize = 1

def processNMon(passSlurmInfo, passNode, passPty):
    # Start nmon process
    command = "ssh {0} -t /mnt/lustre/hcgs/anthonyw/bin/nmon".format(passSlurmInfo['nodes'][passNode]).split(' ')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=passPty)

    # Change pty size to match terminal (
    sizeBuffer = array.array('h', [0, 0, 0, 0])
    fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, sizeBuffer, True)
    fcntl.ioctl(passPty, termios.TIOCSWINSZ, sizeBuffer)

    buffer = ''
    while process.poll() is None:
        out = process.stdout.read(1)
        sys.stdout.write(out.decode('utf-8'))

def main(passJob):
    # Obtain info, check for invalid/pending jobs
    slurmInfo = getSlurmInfo(passJob)

    if not slurmInfo:
        sys.stdout.write("Invalid job ID\r\n")
        return

    if slurmInfo['status'] == 'PENDING':
        sys.stdout.write("Job in pending state\r\n")
        return

    # Default to first node
    main.monitor = 0
   
    # Spawn threads to process output asynchronously 
    pThreads = list()
    for nodeIdx in range(len(slurmInfo['nodes'])):
        # Create pseudo-TTY for this node
        masterPty, slavePty = pty.openpty()
        thread = Thread(target=processTop, args=(slurmInfo, nodeIdx, slavePty))

        # Store thread and handle to master pty
        pThreads.append((thread, os.fdopen(masterPty, 'w')))
        pThreads[-1][0].start()

    # Process input
    while True:
        key = sys.stdin.read(1)

        # Intercept q and ctrl-c, and issue to all nodes
        if key == 'q' or ord(key) == 0x03:
            for pThread in pThreads:
                pThread[1].write(key)
                pThread[1].flush()
            break

        # Intercept [ ] for rotating monitoring, send space for refresh
        if key == ']':
            main.monitor = (main.monitor + 1) % len(slurmInfo['nodes'])
            key = ' '
        if key == '[':
            main.monitor = (main.monitor - 1) % len(slurmInfo['nodes'])
            key = ' '

        # Write any other keys to top
        pThreads[main.monitor][1].write(key)
        pThreads[main.monitor][1].flush()

    for pThread in pThreads: pThread[0].join()
       
# Parse arguments
argParser = argparse.ArgumentParser(description='Slurm Top')
argParser.add_argument('job', help='Slurm job ID')
arguments = argParser.parse_args()

# Set stdin for raw, allowing for keypresses
stdinHandle = sys.stdin.fileno()
ttyOrig = termios.tcgetattr(stdinHandle)
tty.setraw(stdinHandle)

# Start processing
main(arguments.job)

# Reset tty
sys.stdout.write(CURSORON_STRING)
termios.tcsetattr(stdinHandle, termios.TCSADRAIN, ttyOrig)
