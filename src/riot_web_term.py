#!/usr/bin/env python3
import os
import pty
import sys
import tty
import select

front_in  = sys.stdin.fileno()
front_out = sys.stdout.fileno()

tty.setraw(front_in)

master_fd, slave_fd = pty.openpty()
pid = os.fork()

if pid == 0:
    os.setsid()
    os.dup2(slave_fd, 0)
    os.dup2(slave_fd, 1)
    os.dup2(slave_fd, 2)
    os.execvp("bash", ["bash", "-i"])

os.close(slave_fd)

input_buffer = b""

while True:
    r, _, _ = select.select([front_in, master_fd], [], [])

    if front_in in r:
        data = os.read(front_in, 1024)
        if not data:
            break

        input_buffer += data
        
        if b"\n" in input_buffer:
            line, _, rest = input_buffer.partition(b"\n")
            input_buffer = rest

            cmd = line.decode(errors="ignore").strip()

            if cmd:
                inject = f"Running {cmd}:\n"
                os.write(front_out, inject.encode())

            os.write(master_fd, line + b"\n")
        else:
            os.write(master_fd, data)
    
    if master_fd in r:
        data = os.read(master_fd, 1024)
        if not data:
            break
        os.write(front_out, data)