#!/usr/bin/env python3
#
# Copyright (c) 2020 Giovanni Baggio
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

"""UPF Service Agent Matchmap Handler."""

import logging
import time

from iptc import Chain
from iptc import Match as IPT_Match
from iptc import Rule
from iptc import Table

from upfserviceagent.handlers.click import write_handler


class MatchMap:

    def __init__(self, ue_subnet, **click_config):

        self.ue_subnet = ue_subnet
        self.click_config = click_config
        self._stop = False

        self._prot_port_supp = {6: "tcp", 17: "udp", 132: "sctp"}

        self.nat_table = None
        self.upf_chain = None

    def start(self):

        self._init_click_upf()
        self._init_netfilter()

    def stop(self):

        self._stop = True

    def _init_click_upf(self):

        while not self._stop:
            try:
                write_handler(**self.click_config,
                              handler="matchmapclear",
                              value="0")
                break
            except:
                logging.info("Waiting for Click UPF to start...")
                time.sleep(5)

    def _init_netfilter(self):

        self.nat_table = Table(Table.NAT)
        prerouting_chain = Chain(self.nat_table, "PREROUTING")

        for rule in prerouting_chain.rules:
            if rule.target.name == "UPF":
                prerouting_chain.delete_rule(rule)

        self.upf_chain = Chain(self.nat_table, "UPF")
        if self.upf_chain in self.nat_table.chains:
            self.upf_chain.flush()
        else:
            self.nat_table.create_chain(self.upf_chain)

        self.nat_table.refresh()

        upf_rule = Rule()
        upf_rule.src = self.ue_subnet
        upf_rule.create_target("UPF")
        prerouting_chain.insert_rule(upf_rule)

        self.nat_table.refresh()

    def add_matchmap(self, match):

        upf_service_match = "%s,%s-%s/%s-%s" % (match["index"],
                                                match["ip_proto_num"],
                                                match["dst_ip"],
                                                match["netmask"],
                                                match["dst_port"])
        status, response = write_handler(**self.click_config,
                                         handler="matchmapinsert",
                                         value=upf_service_match)

        if status != 200:
            raise Exception(response)

        if match["new_dst_ip"]:
            self._add_rewrite_rule(match)
        else:
            self._add_dummy_rule(match)

    def _add_rewrite_rule(self, match):

        rule = self._get_base_rule(match)

        rule.create_target("DNAT")
        rule.target.to_destination = match["new_dst_ip"]

        if match["new_dst_port"] != 0:
            rule.target.to_destination += ":%s" % match["new_dst_port"]

        logging.debug("Inserting new rule: %s at index: %s"
                      % (rule, match["index"]))
        self.upf_chain.insert_rule(rule, match["index"])
        self.nat_table.refresh()

    def _add_dummy_rule(self, match):

        rule = self._get_base_rule(match)

        rule.create_target("ACCEPT")

        logging.debug("Inserting new rule: %s at index: %s"
                      % (rule, match["index"]))
        self.upf_chain.insert_rule(rule, match["index"])
        self.nat_table.refresh()

    def _get_base_rule(self, match):

        rule = Rule()
        rule.protocol = match["ip_proto_num"]
        rule.dst = "%s/%s" % (match["dst_ip"], match["netmask"])

        if match["dst_port"] != 0:
            ipt_match = IPT_Match(rule, self._prot_port_supp[match["ip_proto_num"]])
            ipt_match["dport"] = str(match["dst_port"])
            rule.add_match(ipt_match)

        return rule

    def delete_matchmap(self, match_index):
        """Delete a match rule."""

        if match_index != -1:
            handler_name = "matchmapdelete"
            self.upf_chain.delete_rule(self.upf_chain.rules[match_index])
        else:
            handler_name = "matchmapclear"
            self.upf_chain.flush()

        status, response = write_handler(**self.click_config,
                                         handler=handler_name,
                                         value=match_index)

        if status != 200:
            raise Exception(response)
