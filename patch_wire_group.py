import json
import patch_wire
import patch_error


class WireGroup(object):
    def __init__(self, name, wire_group_data, ofp_version="OpenFlow10"):
        self.name = name
        self.wire_group_data = wire_group_data
        self.ofp_version = ofp_version
        try:
            self.id = self.wire_group_data['id']
            self.wires = self.wire_group_data['wires']
        except KeyError as err:
            msg = "Wire group:%s does not have key:%s" % (self.name, err.message)
            raise patch_error.PatchDefinitionError(msg)

    def __str__(self):
        return "WireGrp: name:%s, id:%d" % (self.name, self.id)

    def dump(self):
        print self
        for wire in self.wires:
            print "  %s" % wire

    def generate_bcast_rule_by_wire_group(self, bcast_wire, out_ports):
        # wire group id (use as mpls label)
        wire_group_id = self.id
        # path of broadcast (DUT edge -> host edge)
        path_elm_pairs = bcast_wire.dut_to_host_port_pair()
        # switch: [rules] dictionary
        flow_rule = {}

        for path_elm_pair in path_elm_pairs:
            rule = {
                # 'dpid': path_elm_pair.in_elm.node,
                # 'inport': path_elm_pair.in_elm.port,
                # 'outport': path_elm_pair.out_elm.port
                'dpid': path_elm_pair.in_elm.node_entity.datapath_id,
                'inport': path_elm_pair.in_elm.port_entity.number,
                'outport': path_elm_pair.out_elm.port_entity.number,
                'eth_dst': 'ff:ff:ff:ff:ff:ff',
                'priority': 16535
            }
            if path_elm_pair.in_elm.port_entity.is_dut_edge_port():
                # at DUT edge switch
                dut_host_port = bcast_wire.dut_host_elm.port_entity
                if dut_host_port.has_vlan():
                    # if DUT port is vlan-trunk
                    rule.update({
                        'vlan_vid': dut_host_port.vlan_id,
                        'set_vlan': wire_group_id
                    })
                else:
                    # if DUT port is vlan-access
                    if self.ofp_version == "OpenFlow13":
                        rule['push_vlan'] = wire_group_id
                    elif self.ofp_version == "OpenFlow10":
                        rule['set_vlan'] = wire_group_id
                    else:
                        msg = "OpenFlow version unknown for generation wire flow rule."
                        raise patch_error.PatchDefinitionError(msg)

            elif path_elm_pair.out_elm.port_entity.is_host_edge_port():
                # at HOST edge switch
                rule.update({
                    'vlan_vid': wire_group_id,
                    'pop_vlan': "true",
                    'outports': out_ports  # multiple outport
                })
                # remove(replace to 'outports' added as default)
                rule.pop('outport')
            else:
                # at inter-switch
                rule.update({
                    'vlan_vid': wire_group_id
                })
            flow_rule[path_elm_pair.in_elm.node] = [rule]
        return flow_rule


class WireManager(object):
    def __init__(self, wire_data):
        ##################################
        self.ofp_version = "OpenFlow10"  # TODO: ofp version selection
        ##################################
        try:
            self._setup_wire_index(wire_data['wire-index'])
            self._setup_wire_group_index(wire_data['wire-group-index'])
        except KeyError as err:
            msg = "Could not find key:%s in wire info" % err.message
            raise patch_error.PatchDefinitionError(msg)
        self._setup_exclusive_wires()

    def _setup_wire_index(self, wire_index_data):
        self.wire_index = {}  # all wire
        for name, data in wire_index_data.items():
            try:
                if data['mode'] == 'shared':
                    self.wire_index[name] = patch_wire.SharedWire(name, data, self.ofp_version)
                elif data['mode'] == 'exclusive':
                    self.wire_index[name] = patch_wire.ExclusiveWire(name, data, self.ofp_version)
                else:
                    msg = "Wire:%s have invalid 'mode'" % name
                    raise patch_error.PatchDefinitionError(msg)
            except KeyError:
                msg = "Wire:%s does not have 'mode'" % name
                raise patch_error.PatchDefinitionError(msg)

    def _setup_wire_group_index(self, wire_group_index_data):
        self.wire_group_index = {}
        for name, data in wire_group_index_data.items():
            self.wire_group_index[name] = WireGroup(name, data, self.ofp_version)

    def wire_by_name(self, wire_name):
        if wire_name in self.wire_index:
            return self.wire_index[wire_name]
        return None

    def _setup_exclusive_wires(self):
        self.exclusive_wire_index = {}  # subset of exclusive mode wire
        for name, wire in self.wire_index.items():
            if wire.is_exclusive():
                self.exclusive_wire_index[name] = wire

    def generate_bcast_outports_by_wire_group(self, wire_group):
        outports = []
        for wire_name in wire_group.wires:
            wire = self.wire_by_name(wire_name)
            # outports.append(wire.path[0].port)
            outports.append(wire.path[0].port_entity.number)
        return outports

    def dump_wires(self):
        for wire_name, wire in self.wire_index.items():
            wire.dump()

    def dump_wire_groups(self):
        for wire_group_name, wire_group in self.wire_group_index.items():
            wire_group.dump()

    def dump_wire_pair_forward(self):
        """ for debug """
        print "# dump_wire_pair_forward (host to DUT)"
        for wire in self.wire_index.values():
            print wire
            for wire_pair in wire.host_to_dut_port_pair():
                print "  %s" % wire_pair

    def dump_wire_pair_backward(self):
        """ for debug """
        print "# dump_wire_pair_backward (DUT to host)"
        for wire in self.wire_index.values():
            print wire
            for wire_pair in wire.dut_to_host_port_pair():
                print "  %s" % wire_pair


if __name__ == '__main__':
    wire_data_file_name = 'wireinfo.json'
    wire_data_file = open(wire_data_file_name, 'r')
    wire_data = json.load(wire_data_file)
    wire_data_file.close()

    wiremgr = WireManager(wire_data)
    wiremgr.dump_wires()
    wiremgr.dump_wire_groups()

    print("# host-to-dut path pair")
    wiremgr.dump_wire_pair_forward()
    print("# dut-to-host path pair")
    wiremgr.dump_wire_pair_backward()
