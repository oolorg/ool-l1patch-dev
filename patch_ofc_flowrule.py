from ryu.ofproto import ether


class FlowRule(object):
    def __init__(self):
        self.matches = {
            'ip': {},
            'arp': {}
        }
        self.action_dic = {
            'ip': [],
            'arp': []
        }
        self.property_dic = {}  # common in ip/arp

        # flag
        self.use_multiple_ethertype = False

    def rules(self):
        ip_rule = {
            'match': self.matches['ip'],
            'actions': self.action_dic['ip']
        }
        ip_rule.update(self.property_dic)

        if not self.use_multiple_ethertype:
            return [ip_rule]

        arp_rule = {
            'match': self.matches['arp'],
            'actions': self.action_dic['arp']
        }
        arp_rule.update(self.property_dic)

        return [arp_rule, ip_rule]

    def _update_with_same_match_rule(self, match_dic):
        for dic in self.matches.values():
            dic.update(match_dic)

    def _update_respective_values(self, arp_match_dic, ip_match_dic):
        self.matches['arp'].update(arp_match_dic)
        self.matches['ip'].update(ip_match_dic)
        self.use_multiple_ethertype = True

    def _append_with_same_action(self, action):
        for acts in self.action_dic.values():
            acts.append(action)

    def _append_respective_values(self, arp_action, ip_action):
        self.action_dic['arp'].append(arp_action)
        self.action_dic['ip'].append(ip_action)
        self.use_multiple_ethertype = True

    # flow property

    def _update_flow_property(self, dic):
        self.property_dic.update(dic)

    def update_priority(self, priority):
        self._update_flow_property({
            'priority': priority
        })

    # match conditions

    def update_match_inport(self, inport):
        self._update_with_same_match_rule({
            'in_port': inport
        })

    # actions

    def action_output(self, outport):
        self._append_with_same_action({
            'type': 'OUTPUT',
            'port': outport
        })


class FlowRuleOF10(FlowRule):
    # match conditions

    def update_match_eth_src(self, eth_src):
        self._update_with_same_match_rule({
            'dl_src': eth_src  # OF1.0
        })

    def update_match_eth_dst(self, eth_dst):
        self._update_with_same_match_rule({
            'dl_dst': eth_dst  # OF1.0
        })

    def update_match_vlan_vid(self, vlan_vid):
        # used for broadcast match ONLY for L1patch
        self._update_with_same_match_rule({
            'dl_vlan': vlan_vid
        })

    # actions

    def action_set_vlan_vid(self, vlan_vid):
        # OF1.0
        # push vlan tag if tag not exists, or modify vid if tag exists
        self._append_with_same_action({
            'type': 'SET_VLAN_VID',
            'vlan_vid': vlan_vid
        })

    def action_pop_vlan(self):
        # OF1.0
        self._append_with_same_action({
            'type': 'STRIP_VLAN'
        })


class FlowRuleOF13(FlowRuleOF10):
    # match conditions

    def update_match_eth_src(self, eth_src):
        self._update_with_same_match_rule({
            'eth_src': eth_src  # OF1.2-
        })

    def update_match_eth_dst(self, eth_dst):
        self._update_with_same_match_rule({
            'eth_dst': eth_dst  # OF1.2-
        })

    def update_match_mpls_label(self, mpls_label):
        # OF1.3-
        self._update_with_same_match_rule({
            'eth_type': ether.ETH_TYPE_MPLS,
            'mpls_label': mpls_label
        })

    def update_match_vlan_vid(self, vlan_vid):
        # used for broadcast match ONLY for L1patch
        # OF1.2-
        self._update_with_same_match_rule({
            'eth_type': ether.ETH_TYPE_ARP,
            'vlan_vid': vlan_vid
        })

    # actions

    def action_set_vlan_vid(self, vlan_vid):
        # for compatibility
        self._action_set_vlan_vid(vlan_vid)

    def action_push_vlan(self, vlan_vid):
        # OF1.2-
        self._action_push_vlan()
        self._action_set_vlan_vid(vlan_vid)

    def _action_push_vlan(self):
        # OF1.2-
        self._append_with_same_action({
            'type': 'PUSH_VLAN',
            'ethertype': ether.ETH_TYPE_8021Q
        })

    def _action_set_vlan_vid(self, vlan_vid):
        # OF1.2-
        self._append_with_same_action({
            'type': 'SET_FIELD',
            'field': 'vlan_vid',
            'value': 0x1000 + vlan_vid
        })

    def action_pop_vlan(self):
        # OF1.2-
        self._update_respective_values(
            {
                'eth_type': ether.ETH_TYPE_ARP
            },
            {
                'eth_type': ether.ETH_TYPE_IP
            }
        )
        self._append_with_same_action({
            'type': 'POP_VLAN'
        })

    def action_push_mpls(self, mpls_label):
        # OF1.3
        self._actions_push_mpls()
        self._action_set_mpls_label(mpls_label)

    def _actions_push_mpls(self):
        # OF1.3
        self._append_with_same_action({
            'type': 'PUSH_MPLS',
            'ethertype': ether.ETH_TYPE_MPLS
        })

    def _action_set_mpls_label(self, mpls_label):
        # OF1.3
        self._append_with_same_action({
            'type': 'SET_FIELD',
            'field': 'mpls_label',
            'value': mpls_label
        })

    def action_pop_mpls(self):
        # OF1.3
        # used for broadcast match ONLY for L1patch
        self._append_with_same_action({
            'type': 'POP_MPLS',
            'ethertype': ether.ETH_TYPE_ARP
        })
