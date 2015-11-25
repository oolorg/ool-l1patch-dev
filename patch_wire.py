import patch_link
import patch_error


class LogicalWire(object):
    def __init__(self, name, wire_data, ofp_version="OpenFlow10"):
        self.name = name
        self.path = []
        self.ofp_version = ofp_version
        try:
            self.mode = wire_data['mode']
            self._setup_wire_elms(wire_data['path'])
            # end points of wire
            self.test_host_elm = patch_link.NodeLinkElement(*wire_data['test-host-port'])
            self.dut_host_elm = patch_link.NodeLinkElement(*wire_data['dut-host-port'])
        except KeyError as err:
            msg = "Wire:%s does not have key:%s" % (self.name, err.message)
            raise patch_error.PatchDefinitionError(msg)

    def _setup_wire_elms(self, wire_data):
        for path_elm_data in wire_data:
            self.path.append(patch_link.NodeLinkElement(*path_elm_data))

    def setup_wire_entity(self, node_mgr):
        """
        map physical info to logical info
        :param node_mgr:
        :return:
        """
        self.test_host_elm.node_entity = node_mgr.node_by_name(
            self.test_host_elm.node
        )
        self.test_host_elm.port_entity = node_mgr.node_port_by_name(
            self.test_host_elm.node, self.test_host_elm.port
        )
        self.dut_host_elm.node_entity = node_mgr.node_by_name(
            self.dut_host_elm.node
        )
        self.dut_host_elm.port_entity = node_mgr.node_port_by_name(
            self.dut_host_elm.node, self.dut_host_elm.port
        )
        for path_elm in self.path:
            path_elm.node_entity = node_mgr.node_by_name(
                path_elm.node
            )
            path_elm.port_entity = node_mgr.node_port_by_name(
                path_elm.node, path_elm.port
            )

    def is_exclusive(self):
        return self.mode == 'exclusive'

    def is_shared(self):
        return self.mode == 'shared'

    def __str__(self):
        return "Wire: %s(%s)" % (self.name, self.mode)

    def generate_flow_rule(self):
        flow_rule = {}
        # forward (Host -> DUT) rule
        self._generate_wire_rule(flow_rule, True)
        # backward (DUT -> Host) rule
        self._generate_wire_rule(flow_rule, False)

        return flow_rule

    def _generate_wire_rule(self, flow_rule, forward=True):
        """" pre-process to generate wire rule """
        if forward:
            path_elm_pairs = self.host_to_dut_port_pair()
        else:
            path_elm_pairs = self.dut_to_host_port_pair()

        test_host_port = self.test_host_elm.port_entity
        dut_host_port = self.dut_host_elm.port_entity
        self._generate_wire_rule_by_path(
            forward, flow_rule, path_elm_pairs, test_host_port, dut_host_port)

    def _generate_wire_rule_by_path(
            self, forward,
            flow_rule, path_elm_pairs, test_host_port, dut_host_port):
        pass  # abstract

    @staticmethod
    def _forward_path_port_pair(path):
        elm_pairs = []
        for i in xrange(len(path) - 1):
            in_elm = path[i]
            out_elm = path[i + 1]
            if in_elm.node == out_elm.node:
                elm_pairs.append(patch_link.NodeLink(in_elm, out_elm))
        if len(elm_pairs) == 0:
            msg = "Path element pairs not found for path:%s" % path
            raise patch_error.PatchDefinitionError(msg)
        return elm_pairs

    @staticmethod
    def _merge_flow_rule(node_name, flow_rule, rule):
        if node_name in flow_rule:
            flow_rule[node_name].append(rule)
        else:
            # initialize as list of rule
            flow_rule[node_name] = [rule]

    def host_to_dut_port_pair(self):
        pass  # abstract

    def dut_to_host_port_pair(self):
        pass  # abstract

    def dump(self):
        print self
        path_elms = [self.test_host_elm] + self.path + [self.dut_host_elm]
        for path_elm in path_elms:
            print "  %s" % path_elm


class ExclusiveWire(LogicalWire):
    def __init__(self, name, wire_data, ofp_version):
        super(ExclusiveWire, self).__init__(name, wire_data, ofp_version)

    def host_to_dut_port_pair(self):
        # exclusive wire has no direction
        return self._forward_path_port_pair(self.path)

    def dut_to_host_port_pair(self):
        # exclusive wire has no direction
        return self._forward_path_port_pair(list(reversed(self.path)))

    def _generate_wire_rule_by_path(
            self, forward,
            flow_rule, path_elm_pairs, test_host_port, dut_host_port):
        for path_elm_pair in path_elm_pairs:
            try:
                rule = {
                    # 'dpid': path_elm_pair.in_elm.node,
                    # 'inport': path_elm_pair.in_elm.port,
                    # 'outport': path_elm_pair.out_elm.port
                    'dpid': path_elm_pair.in_elm.node_entity.datapath_id,
                    'inport': path_elm_pair.in_elm.port_entity.number,
                    'outport': path_elm_pair.out_elm.port_entity.number,
                    'priority': 65535
                }
                # merge
                self._merge_flow_rule(path_elm_pair.in_elm.node, flow_rule, rule)
            except AttributeError as err:
                msg = "Node or Port definition missing in path_elm:%s" % path_elm_pair
                raise patch_error.PatchDefinitionError(msg)


class SharedWire(LogicalWire):
    def __init__(self, name, wire_data, ofp_version):
        super(SharedWire, self).__init__(name, wire_data, ofp_version)

    def host_to_dut_port_pair(self):
        head_port = self.path[0].port_entity
        tail_port = self.path[-1].port_entity
        if head_port.is_host_edge_port() and tail_port.is_dut_edge_port():
            return self._forward_path_port_pair(self.path)
        elif head_port.is_dut_edge_port() and tail_port.is_host_edge_port():
            return self._forward_path_port_pair(list(reversed(self.path)))
        else:
            msg = "wire head/tail is same type: dut-edge or host-edge"
            raise patch_error.PatchDefinitionError(msg)

    def dut_to_host_port_pair(self):
        head_port = self.path[0].port_entity
        tail_port = self.path[-1].port_entity
        if head_port.is_host_edge_port() and tail_port.is_dut_edge_port():
            return self._forward_path_port_pair(list(reversed(self.path)))
        elif head_port.is_dut_edge_port() and tail_port.is_host_edge_port():
            return self._forward_path_port_pair(self.path)
        else:
            msg = "wire head/tail is same type: dut-edge or host-edge"
            raise patch_error.PatchDefinitionError(msg)

    @staticmethod
    def __use_vlan(path_elm_pair, dut_host_port, forward):
        port_entity = path_elm_pair.out_elm.port_entity\
            if forward else path_elm_pair.in_elm.port_entity
        return port_entity.is_dut_edge_port() and dut_host_port.has_vlan()

    def _generate_wire_rule_by_path(
            self, forward,
            flow_rule, path_elm_pairs, test_host_port, dut_host_port):

        match_eth = 'eth_src' if forward else 'eth_dst'
        host_mac = test_host_port.mac_addr

        for path_elm_pair in path_elm_pairs:
            rule = {
                # 'dpid': path_elm_pair.in_elm.node,
                # 'inport': path_elm_pair.in_elm.port,
                # 'outport': path_elm_pair.out_elm.port,
                'dpid': path_elm_pair.in_elm.node_entity.datapath_id,
                'inport': path_elm_pair.in_elm.port_entity.number,
                'outport': path_elm_pair.out_elm.port_entity.number,
                match_eth: host_mac,
                'priority': 32767
            }

            # select action at dut-edge by direction: push/pop vlan
            if self.__use_vlan(path_elm_pair, dut_host_port, forward):
                # print "## %s, %s, %s" % (path_elm_pair, dut_host_port, forward)
                if forward:
                    if self.ofp_version == "OpenFlow13":
                        rule['push_vlan'] = dut_host_port.vlan_id
                    elif self.ofp_version == "OpenFlow10":
                        rule['set_vlan'] = dut_host_port.vlan_id
                    else:
                        msg = "OpenFlow version unknown for generation wire flow rule."
                        raise patch_error.PatchDefinitionError(msg)
                else:
                    rule['vlan_vid'] = dut_host_port.vlan_id
                    rule['pop_vlan'] = "true"
            # merge
            self._merge_flow_rule(path_elm_pair.in_elm.node, flow_rule, rule)
