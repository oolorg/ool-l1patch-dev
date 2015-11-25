import json
import time
import re
import subprocess
import collections
import logging
import signal
from functools import partial
from mininet.cli import CLI
from mininet.node import RemoteController, OVSSwitch
from mininet.net import Mininet
from mininet.link import Link
from mininet.link import Intf
import patch_node
import scenario_error


class TestHostParam(object):
    def __init__(self, mn_host, host_obj, port_obj):
        self.mn_host = mn_host
        self.host = host_obj
        self.port = port_obj

    def setup(self):
        self.mn_host.intf(self.port.name).setMAC(self.port.mac_addr)
        self.mn_host.intf(self.port.name).setIP(self.port.ip_addr)
        if self.port.gateway:
            cmd = "ip route add via %s" % self.port.gateway
            self.mn_host.cmd(cmd)

    def __str__(self):
        return "test host %s[%s] = MAC:%s, IP:%s, Gateway:%s" % (
            self.host.name, self.port.name,
            self.port.mac_addr, self.port.ip_addr, self.port.gateway
        )


class ScenarioTesterBase(object):
    def __init__(self, testdefs_file_name):
        self.logger = logging.getLogger(__name__)
        self.testdef_data = {}  # parameter dict of scenario test
        self._set_testdef_data(testdefs_file_name)
        self._set_test_env_params()
        self._set_l1patch_data()
        self.orig_handler = signal.getsignal(signal.SIGINT)

        # test host params
        self.test_host_params = []
        # config mininet
        switch = partial(OVSSwitch, protocols=self.ofp_version)
        self.net = Mininet(switch=switch)
        c0 = RemoteController('c0')
        self.net.addController(c0)

    def _set_testdef_data(self, testdefs_file_name):
        try:
            testdefs_file = open(testdefs_file_name, "r")
            self.testdef_data = json.load(testdefs_file)
            testdefs_file.close()
        except IOError as err:
            msg = "Cannot open test definition file: %s\n%s" % (testdefs_file_name, err)
            raise scenario_error.ScenarioTestError(msg)

    def dump_testdef_data(self):
        # for debug
        print json.dumps(self.testdef_data, indent=2)

    def _set_l1patch_data(self):
        try:
            params = self.testdef_data["l1patch-defs"]
            # node info
            self._set_node_mgr(params["physical-info-file"])
            # generate flow-rules files
            gen_exc_wire_flows_cmd = self._make_command(
                params, "generate-exclusive-wire-flows-command"
            )
            gen_shd_wire_flows_cmd = self._make_command(
                params, "generate-shared-wire-flows-command"
            )
            self._exec_command(gen_exc_wire_flows_cmd)
            self._exec_command(gen_shd_wire_flows_cmd)
            # set flow-rules ops command
            self.put_exc_wire_flows_cmd = self._make_command(
                params, "put-exclusive-wire-flows-command"
            )
            self.del_exc_wire_flows_cmd = self._make_command(
                params, "delete-exclusive-wire-flows-command"
            )
            self.put_shd_wire_flows_cmd = self._make_command(
                params, "put-shared-wire-flows-command"
            )
            self.del_shd_wire_flows_cmd = self._make_command(
                params, "delete-shared-wire-flows-command"
            )
        except KeyError as err:
            msg = "Cannot find key:%s in test definition 'l1patch-defs' section." % err.message
            raise scenario_error.ScenarioTestDefinitionError(msg)

    def _set_test_env_params(self):
        try:
            params = self.testdef_data["test-env-params"]
            self.mn_ext_intfs = params["mininet-external-interfaces"]
            self.ofp_version = params["ofs-openflow-version"]
        except KeyError as err:
            msg = "Cannot find key:%s in test definition 'test-env-params' section." % err.message
            raise scenario_error.ScenarioTestDefinitionError(msg)

    @staticmethod
    def _make_command(data, cmd_key):
        cmd = data[cmd_key]
        for param in re.findall(r"@([_\w\d\-]+)@", cmd):
            param_key = param + "-file"
            try:
                param_val = data[param_key]
            except KeyError:
                msg = "Cannot find param:%s -> key:@%s@ in command-key:%s" % (
                    param, param_key, cmd_key
                )
                raise scenario_error.ScenarioTestDefinitionError(msg)
            replacement = "@%s@" % param
            cmd = cmd.replace(replacement, param_val)
        return cmd

    def _exec_command(self, cmd):
        self.logger.info("exec command: %s", cmd)
        subprocess.check_call(cmd, shell=True)

    def _run_command_at(self, host, cmd):
        self.logger.info("run @`%s`: `%s`", host.name, cmd)
        return host.cmd(cmd)

    def _set_node_mgr(self, node_info_file_name):
        try:
            node_data_file = open(node_info_file_name, "r")
            # use OrderedDict to keep order defined in config file
            node_data = json.load(
                node_data_file, object_pairs_hook=collections.OrderedDict
            )
            node_data_file.close()
            self.node_mgr = patch_node.NodeManager(node_data)
        except IOError as err:
            raise err  # TODO

    def _build_test_host(self, mn_switch):
        for host_name, host_obj in self.node_mgr.test_host_index.items():
            host = self.net.addHost(host_name)
            # host interface was created when Link-ed switch
            Link(host, mn_switch)
            for port_name, port_obj in host_obj.port_index.items():
                # TODO: suppose that host has ONLY one interface
                thp = TestHostParam(host, host_obj, port_obj)
                self.logger.info("build test host: %s", thp)
                self.test_host_params.append(thp)

    def _setup_test_host_intf(self):
        # MUST called after net.build()
        for test_host_param in self.test_host_params:
            test_host_param.setup()

    def _start_mininet(self):
        self.net.start()
        time.sleep(1)

    def _stop_mininet(self):
        time.sleep(1)
        self.net.stop()

    def _delete_flow_rules(self):
        time.sleep(1)
        # delete only shared (mininet-hosts) wire to continue test
        # self._exec_command(self.del_exc_wire_flows_cmd)
        self.logger.info("delete shared-wire-flow-rules")
        self._exec_command(self.del_shd_wire_flows_cmd)

    def _put_layer1_flow_rules(self):
        self.logger.info("put exclusive-wire-flow-rules")
        self._exec_command(self.put_exc_wire_flows_cmd)

    def _put_layer2_flow_rules(self):
        self.logger.info("put shared-wire-flow-rules")
        self._exec_command(self.put_shd_wire_flows_cmd)

    def _add_external_nic(self, mn_switch):
        for interface in self.mn_ext_intfs:
            Intf(interface, node=mn_switch)

    def _run_cli(self):
        signal.signal(signal.SIGINT, self.orig_handler)
        CLI(self.net)

    def _run_cli_by_signal(self, signum, frame):
        self.logger.info("change mode to CLI by signal:%s", signum)
        self._run_cli()

    def _set_sigint_handler(self):
        # add signal handler to suspend auto scenario test
        signal.signal(signal.SIGINT, self._run_cli_by_signal)

    def _build_mininet(self):
        # default topology:
        # all test-hosts connect to mininet managed OVS:s1.
        # MUST override this function to modify mininet topology
        s1 = self.net.addSwitch('s1')
        self._build_test_host(s1)
        self.net.build()

        # set interface parameters
        # so set interface parameters after build()
        # because net.build() reset host IP address...
        self._setup_test_host_intf()
        # add interface to connect real(external) network
        self._add_external_nic(s1)

    def _run_test(self, opt_dic):
        # abstract
        self._build_mininet()
        self._start_mininet()
        self._run_cli()
        self._stop_mininet()

    def run_test(self, opt_dic):
        self.logger.info("Start run_test()")
        self._run_test(opt_dic)
        self.logger.info("Stop run_test()")
