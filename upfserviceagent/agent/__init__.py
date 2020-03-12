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

"""UPF Service Agent Package."""

PT_VERSION = 0

# agent to manager
PT_HELLO = "hello"
PT_UE_MAP = "ue_map"
PT_MATCH_OK = "match_ok"
PT_MATCH_KO = "match_ko"

# manager to agent
PT_MATCH_ADD = "match_add"
PT_MATCH_DELETE = "match_delete"
