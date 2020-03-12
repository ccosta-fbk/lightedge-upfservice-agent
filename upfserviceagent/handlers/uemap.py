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

"""UPF Service Agent UEmap Handler."""

from upfserviceagent.handlers.click import read_handler


def get_uemap(**config):

    status, response = read_handler(**config, handler="uemap")

    if status != 200:
        raise Exception(response)

    fields = ["ue_ip", "enb_ip", "teid_downlink", "epc_ip", "teid_uplink"]
    uemap = dict()

    for ue_entry in response.split('\n'):
        if ue_entry != "":
            ue_dict = dict(zip(fields, ue_entry.split(',')))
            uemap[ue_dict["ue_ip"]] = ue_dict

    return uemap
