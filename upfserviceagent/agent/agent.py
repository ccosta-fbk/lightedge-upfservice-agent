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

"""The UPF Service Agent."""

import time
import logging
import sys
import json

from argparse import ArgumentParser

import websocket
from threading import Thread
from uuid import uuid4

from upfserviceagent.agent import PT_VERSION
from upfserviceagent.agent import PT_HELLO
from upfserviceagent.agent import PT_UE_MAP
from upfserviceagent.agent import PT_MATCH_ACTION_RESULT
from upfserviceagent.handlers.uemap import get_uemap
from upfserviceagent.handlers.matchmap import MatchMap


UPF_SERVICE_MANAGER_ADDRESS = "127.0.0.1"
UPF_SERVICE_MANAGER_PORT = 7000
UPF_SERVICE_MANAGER_EVERY = 5
UPF_SERVICE_ADDRESS = "127.0.0.1"
UPF_SERVICE_PORT = 7777
UPF_SERVICE_ELEMENT = "upfr"
UPF_SERVICE_UE_SUBNET = "10.0.0.0/8"
UPF_SERVICE_EVERY = 2


def get_uuid():
    return str(uuid4())


def dump_message(message):
    """Dump a generic message.

    Args:
        message, a message

    Returns:
        None
    """

    header = "Received %s, uuid %s" % (message['type'], message['uuid'])

    del message['version']
    del message['type']

    fields = ["%s=%s" % (k, v)for k, v in message.items()]
    logging.info("%s (%s)", header, ", ".join(fields))


def on_open(websock):
    """ Called when the web-socket is opened. """

    logging.info("Socket %s opened...", websock.url)


def on_message(websock, message):
    """ Called on receiving a new message. """

    try:
        msg = json.loads(message)
        websock.handle_message(msg)
    except ValueError as ex:
        logging.info("Invalid input: %s", ex)
        logging.info(message)


def on_close(websock):
    """ Called when the web-socket is closed. """

    logging.info("Socket %s closed...", websock.url)


class UPFServiceAgent(websocket.WebSocketApp):
    """The UPF Service Agent.

    # us = UPF Service
    # usm = UPF Service Manager

    Attributes:
        usm_addr: The UPF Service Manager address
        usm_port: The UPF Service Manager port
        usm_every: The hello period toward the UPF Service Manager
        us_addr: The UPF Service address
        us_port: The UPF Service port
        us_element: The UPF Service click element name
        us_ue_subnet: The UE subnet to be considered by the UPF Service
        us_every: The UPF Service UE list's polling period
    """

    def __init__(self, url, usm_addr, usm_port, usm_every, us_addr, us_port,
                 us_element, us_ue_subnet, us_every, logdir):

        super().__init__(url)

        self._stop = False
        self.usm_addr = usm_addr
        self.usm_port = usm_port
        self.usm_every = usm_every
        self.us_addr = us_addr
        self.us_port = us_port
        self.us_element = us_element
        self.us_ue_subnet = us_ue_subnet
        self.us_every = us_every
        self.on_open = None
        self.on_close = None
        self.on_message = None
        self.logdir = logdir
        self.matchmap = None

        self.click_config = {"host": self.us_addr,
                             "port": self.us_port,
                             "element": self.us_element}

        logging.info("Initializing the UPF Service Agent...")

        self._init_upf_service()
        self._init_periodic_tasks()

    def stop(self):
        """ Stop the threads. """

        self._stop = True
        self.matchmap.stop()

    def _init_upf_service(self):
        """Init matchmap handler, block until the UPF Service is available. """

        self.matchmap = MatchMap(self.us_ue_subnet, **self.click_config)
        self.matchmap.start()

    def _init_periodic_tasks(self):
        """Init threads. """

        hello_sender = Thread(target=self._send_periodic_hello)
        hello_sender.start()
        uemap_poller = Thread(target=self._uemap_poller)
        uemap_poller.start()

    def _send_periodic_hello(self):
        """Hello sender thread handler. """

        while not self._stop:

            try:
                self.send_hello()
            except Exception as ex:
                logging.info("Cannot send hello")
            finally:
                time.sleep(self.usm_every)

    def _uemap_poller(self):
        """UEMap poller thread handler. """

        while not self._stop:

            try:
                uemap = get_uemap(**self.click_config)
                self.send_ue_map(uemap)
            except Exception as ex:
                logging.info("Cannot send ue map updates")
            finally:
                time.sleep(self.us_every)

    def send_message(self, message_type, message, uuid):
        """Add fixed header fields and send message. """

        message['version'] = PT_VERSION
        message['type'] = message_type
        message['uuid'] = uuid

        logging.info("Sending %s, uuid %s", message['type'], message['uuid'])

        msg = json.dumps(message)
        self.send(msg)

    def send_hello(self):
        """ Send HELLO message. """

        hello = {'every': self.usm_every}
        self.send_message(PT_HELLO, hello, get_uuid())

    def send_ue_map(self, ue_map):
        """ Send UE_MAP message. """

        self.send_message(PT_UE_MAP, ue_map, get_uuid())

    def send_match_action_result(self, match_index, status, uuid, reason=None):
        """ Send MATCH_ACTION_RESULT message. """

        result = {'match_index': match_index,
                  'status': status,
                  'reason': reason}
        self.send_message(PT_MATCH_ACTION_RESULT, result, uuid)

    def handle_message(self, msg):
        """ Handle incoming message (as a Python dict). """

        handler_name = "_handle_%s" % msg['type']

        if not hasattr(self, handler_name):
            logging.info("Unknown message type: %s", msg['type'])
            return

        handler = getattr(self, handler_name)
        handler(msg)

    def _handle_match_add(self, message):
        """Handle MATCH_ADD message.

        Args:
            message, a MATCH_ADD message
        Returns:
            None
        """

        dump_message(message)

        status = 201
        reason = None
        index = -1

        try:
            index = message["match"]["index"]
            self.matchmap.add_matchmap(message["match"])

        except KeyError as ex:
            status = 404
            reason = str(ex)
        except ValueError as ex:
            status = 400
            reason = str(ex)
        except Exception as ex:
            status = 500
            reason = str(ex)
        finally:

            if status == 201:
                self.send_match_action_result(index, status, message["uuid"])
            else:
                logging.info("Exception while adding matchmap: %s" % reason)
                self.send_match_action_result(index, 500, message["uuid"],
                                              reason=reason)

    def _handle_match_delete(self, message):
        """Handle MATCH_DELETE message.

        Args:
            message, a MATCH_DELETE message
        Returns:
            None
        """

        dump_message(message)

        status = 204
        reason = None
        index = -1

        try:
            index = message["match_index"]
            self.matchmap.delete_matchmap(message["match_index"])

        except KeyError as ex:
            status = 404
            reason = str(ex)
        except Exception as ex:
            status = 500
            reason = str(ex)
        finally:

            if status == 204:
                self.send_match_action_result(index, status, message["uuid"])
            else:
                logging.info("Exception while deleting matchmap: %s" % reason)
                self.send_match_action_result(index, 500, message["uuid"],
                                              reason=reason)


def main():
    """Parse the command line and set the callbacks."""

    usage = "%s [options]" % sys.argv[0]

    parser = ArgumentParser(usage=usage)

    parser.add_argument("-l", "--logdir", dest="logdir", default=None,
                        help="Logfile; default=None")

    parser.add_argument("-ma", "--usm_addr", dest="usm_addr",
                        default=UPF_SERVICE_MANAGER_ADDRESS,
                        help="UPF Service Manager address; default=%s"
                             % UPF_SERVICE_MANAGER_ADDRESS)

    parser.add_argument("-mp", "--usm_port", dest="usm_port",
                        default=UPF_SERVICE_MANAGER_PORT,
                        help="UPF Service Manager port; default=%s"
                             % UPF_SERVICE_MANAGER_PORT)

    parser.add_argument("-me", "--usm_every", dest="usm_every",
                        default=UPF_SERVICE_MANAGER_EVERY,
                        help="UPF Service Manager keepalive period; default=%s"
                             % UPF_SERVICE_MANAGER_EVERY)

    parser.add_argument("-a", "--us_addr", dest="us_addr",
                        default=UPF_SERVICE_ADDRESS,
                        help="UPF Service address; default=%s"
                             % UPF_SERVICE_ADDRESS)

    parser.add_argument("-p", "--us_port", dest="us_port",
                        default=UPF_SERVICE_PORT,
                        help="UPF Service port; default=%s"
                             % UPF_SERVICE_PORT)

    parser.add_argument("-ce", "--us_element", dest="us_element",
                        default=UPF_SERVICE_ELEMENT,
                        help="UPF Service click element name; default=%s"
                             % UPF_SERVICE_ELEMENT)

    parser.add_argument("-s", "--us_ue_subnet", dest="us_ue_subnet",
                        default=UPF_SERVICE_UE_SUBNET,
                        help="UPF Service UE subnet; default=%s"
                             % UPF_SERVICE_UE_SUBNET)

    parser.add_argument("-e", "--us_every", dest="us_every",
                        default=UPF_SERVICE_EVERY,
                        help="UPF Service keepalive period; default=%s"
                             % UPF_SERVICE_EVERY)

    (args, _) = parser.parse_known_args(sys.argv[1:])

    if args.logdir:
        logging.basicConfig(filename=args.logdir + "/agent.log",
                            level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.DEBUG)

    url = "ws://%s:%u/" % (args.usm_addr, args.usm_port)
    agent = UPFServiceAgent(url, args.usm_addr, args.usm_addr, args.usm_every,
                            args.us_addr, args.us_port, args.us_element,
                            args.us_ue_subnet, args.us_every, args.logdir)

    agent.on_open = on_open
    agent.on_message = on_message
    agent.on_close = on_close

    stop = False

    while not stop:
        try:
            logging.info("Trying to connect to manager %s", url)
            agent.run_forever()
            logging.info("Unable to connect, retrying in %us", agent.usm_every)
            time.sleep(agent.usm_every)
        except KeyboardInterrupt:
            agent.stop()
            stop = True


if __name__ == "__main__":
    main()
