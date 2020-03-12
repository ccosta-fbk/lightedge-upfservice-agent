#!/usr/bin/env python3
#
# Copyright (c) 2020 Fondazione Bruno Kessler
# Author(s): Giovanni Baggio (g.baggio@fbk.eu)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

"""UPF Service Agent Click Handler."""

import socket
import re


def write_handler(host, port, element, handler, value):
    """Write to a click handler."""

    sock = socket.socket()
    sock.connect((host, port))

    f_hand = sock.makefile()
    line = f_hand.readline()

    if line != "Click::ControlSocket/1.3\n":
        raise ValueError("Unexpected reply: %s" % line)

    cmd = "write %s.%s %s\n" % (element, handler, value)
    sock.send(cmd.encode("utf-8"))

    line = f_hand.readline()

    regexp = '([0-9]{3}) (.*)'
    match = re.match(regexp, line)

    while not match:
        line = f_hand.readline()
        match = re.match(regexp, line)

    groups = match.groups()

    return (int(groups[0]), groups[1])


def read_handler(host, port, element, handler):
    """Read a click handler."""

    sock = socket.socket()
    sock.connect((host, port))

    f_hand = sock.makefile()
    line = f_hand.readline()

    if line != "Click::ControlSocket/1.3\n":
        raise ValueError("Unexpected reply: %s" % line)

    cmd = "read %s.%s\n" % (element, handler)
    sock.send(cmd.encode("utf-8"))

    line = f_hand.readline()

    regexp = '([0-9]{3}) (.*)'
    match = re.match(regexp, line)

    while not match:
        line = f_hand.readline()
        match = re.match(regexp, line)

    groups = match.groups()

    if int(groups[0]) == 200:

        line = f_hand.readline()
        res = line.split(" ")

        length = int(res[1])
        data = f_hand.read(length)

        return (int(groups[0]), data)

    return (int(groups[0]), line)
