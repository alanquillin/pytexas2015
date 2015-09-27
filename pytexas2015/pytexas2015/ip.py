from netaddr import IPNetwork


def ipv4_to_int(string):
    cidr_idx = string.find('/')
    if cidr_idx == -1:
        ip = string.split('.')
        assert len(ip) == 4
        i = 0
        for b in ip:
            b = int(b)
            i = (i << 8) | b
        return i

    i = ipv4_to_int(string[0:cidr_idx])
    m = cidr_mask_to_net_mask(int(string[cidr_idx + 1:]))
    return i, m


def cidr_mask_to_net_mask(cidr_mask):
    return (1 << 32) - (1 << (32 - cidr_mask))


def convert_to_cidr_32_blocks(blocks):
    cidr_32_blocks = []
    if isinstance(blocks, list):
        for block in blocks:
            cidr_32_blocks.extend(convert_to_cidr_32_blocks(block))
    else:
        ip_network = IPNetwork(blocks)
        if len(ip_network) <= 2:
            cidr_32_blocks.append("%s/32" % str(ip_network.ip))
        else:
            network_addr = ip_network.network
            broadcast_addr = ip_network.broadcast
            for ip in ip_network:
                if ip != network_addr and ip != broadcast_addr:
                    cidr_32_blocks.append("%s/32" % ip)

    return cidr_32_blocks
