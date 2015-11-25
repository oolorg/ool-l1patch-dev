class NodeLinkElement(object):
    def __init__(self, node_name, port_name):
        self.node = node_name
        self.port = port_name
        self.port_entity = None  # NodePort object
        self.node_entity = None

    def __str__(self):
        return "LinkElm: [%s, %s]" % (self.node, self.port)

    def __eq__(self, other):
        return self.node == other.node and self.port == other.port


class NodeLink(object):
    def __init__(self, endpoint1, endpoint2):
        self.endpoint1 = endpoint1
        self.endpoint2 = endpoint2
        self.in_elm = endpoint1  # alias
        self.out_elm = endpoint2  # alias

    def counterpart(self, link_elm):
        if link_elm == self.endpoint1:
            return self.endpoint2
        elif link_elm == self.endpoint2:
            return self.endpoint1
        return None

    def counterpart_by_name(self, node_name, port_name):
        link_elm = NodeLinkElement(node_name, port_name)
        return self.counterpart(link_elm)

    def has_endpoint(self, link_elm):
        return link_elm == self.endpoint1 or link_elm == self.endpoint2

    def has_endpoint_by_name(self, node_name, port_name):
        link_elm = NodeLinkElement(node_name, port_name)
        return self.has_endpoint(link_elm)

    def __str__(self):
        return "Link: [%s, %s]" % (self.endpoint1, self.endpoint2)


class NodeLinkManager(object):
    def __init__(self, link_data):
        self.link_data = link_data  # link list data
        self.links = []
        self._setup_links()

    def _setup_links(self):
        for link in self.link_data:
            endpoint1 = NodeLinkElement(*link[0])
            endpoint2 = NodeLinkElement(*link[1])
            self.links.append(NodeLink(endpoint1, endpoint2))

    def find_link(self, link_elm):
        for link in self.links:
            if link.has_endpoint(link_elm):
                return link
        return None

    def find_link_by_name(self, node_name, port_name):
        link_elm = NodeLinkElement(node_name, port_name)
        return self.find_link(link_elm)

    def dump(self):
        for link in self.links:
            print "  %s" % link
