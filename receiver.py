import argparse, socket, time, os, struct, csv

# from hudp.api import GameNetAPI
def checksum(msg_bytes):
    """Compute 16-bit Internet checksum."""
    s = 0
    # Process 16-bit chunks
    for i in range(0, len(msg_bytes), 2):
        if i + 1 < len(msg_bytes):
            w = (msg_bytes[i] << 8) + msg_bytes[i + 1]
        else:
            w = (msg_bytes[i] << 8)
        s += w

    # Wrap-around carry bits
    s = (s >> 16) + (s & 0xffff)
    s += (s >> 16)
    return ~s & 0xffff

def compute_udp_checksum(src_ip, dest_ip, udp_header, payload):
    """
    Compute UDP checksum including pseudo-header.
    Payload = custom_header + mock_game_data
    """
    # Pseudo header fields
    src_addr = socket.inet_aton(src_ip)
    dest_addr = socket.inet_aton(dest_ip)
    placeholder = 0 # padding byte to ensure pseudo_header is 16 bytes long
    protocol = socket.IPPROTO_UDP
    udp_length = len(udp_header) + len(payload)

    pseudo_header = struct.pack('!4s4sBBH', src_addr, dest_addr, placeholder, protocol, udp_length) # for computing checksum only

    # Combine everything
    checksum_input = pseudo_header + udp_header + payload

    return checksum(checksum_input)

def validate_checksum(src_ip, dest_ip, udp_header, payload):
    """Return True if checksum valid, else False."""
    received_checksum = struct.unpack('!HHHH', udp_header)[3] # checksum is 4th field in udp_header

    # Zero the checksum field for recomputation of checksum
    header_zeroed = udp_header[:6] + struct.pack('!H', 0)
    computed = compute_udp_checksum(src_ip, dest_ip, header_zeroed, payload)

    return received_checksum == computed

def unpack_packet(udp_packet):
    udp_header = udp_packet[:8] # header is first 8 bytes
    payload = udp_packet[8:]

    src_port, dest_port, udp_length, checksum = struct.unpack('!HHHH', udp_header)

    return {
        'udp_header': udp_header,
        'src_port': src_port,
        'dest_port': dest_port,
        'udp_length': udp_length,
        'checksum': checksum,
        'payload': payload
    }

def unpack_payload(payload): # might need to change later depending on payload structure
    """
    Payload: custom_header + mock_game_data
    custom_header: flags(channel_type 0/1 RMB, latency 0/1 2nd RMB) [1B] | seq_no [2B] | timestamp (time sent) [4B] <total 7B long>
    mock_game_data:
    """
    custom_header = payload[:7]
    mock_game_data = payload[7:]

    flags, seq_no, timestamp = struct.unpack('!BHI', custom_header)

    channel_type = flags & 0b00000001 # 0 for reliable and 1 for unreliable
    latency = (flags & 0b00000010) >> 1 # 0 for low and 1 for high
    

    return {
        'channel_type': channel_type,
        'latency': latency,
        'seq_no': seq_no,
        'timestamp': timestamp,
        'mock_game_data': mock_game_data
    }

def make_packet(src_ip, dest_ip, src_port, dest_port, payload):
    """
    Returns UDP ACK packet for sending
    Payload = seq_no
    """
    temporary_checksum = 0 # for computing actual checksum
    udp_length = 8 + len(payload)
    udp_header = struct.pack('!HHHH', src_port, dest_port, udp_length, temporary_checksum)

    # compute checksum
    checksum = compute_udp_checksum(src_ip, dest_ip, udp_header, payload)

    # rebuild final header with real checksum
    udp_header = struct.pack('!HHHH', src_port, dest_port, udp_length, checksum)

    packet = udp_header + payload

    return packet

def send_ack(socket, ack_packet, dest_ip, dest_port):
    """Send ack if received reliable packet"""
    socket.sendto(ack_packet, (dest_ip, dest_port))

def open_new_csv_file(file, fieldnames):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, 'w', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()  

def write_to_csv_file(file, fieldnames, row):
    with open(file, 'a', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writerow(row)
        csv_file.flush()

CSV_FIELDNAMES = ['Channel', 'Packet Number', 'Time Sent', 'Time Received','RTT Unreliable', 'Time ACK Received', 'RTT Reliable']

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", default="logs/session.csv")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    # Open new CSV file
    open_new_csv_file(args.log, CSV_FIELDNAMES)

    # api = GameNetAPI(sock, peer=None, log_path=args.log)

    def on_rel(b: bytes):
        # keep small and visible
        # send ack
        pass

    def on_unrel(b: bytes):
        pass

    # api.set_callbacks(on_rel, on_unrel)
    # api.start()
    print(f"Receiver listening on {args.bind}:{args.port}. Logs -> {args.log}")
    try:
        while True:
            packet, address = sock.recvfrom(2048)
            if address == sock.getsockname():
                continue # ignore packets sent from self
            
            packet_info = unpack_packet(packet)
            payload_info = unpack_payload(packet_info['payload'])

            reliable = True if payload_info['channel_type'] == 0 else False
            checksum_valid = validate_checksum(address[0], sock.getsockname()[0], packet_info['udp_header'], packet_info['payload'])

            if checksum_valid:
                print(f"Received packet {payload_info['seq_no']}")
                if reliable:
                    # send ack only if reliable
                    ack_payload = struct.pack('!H', payload_info['seq_no'])
                    ack_packet = make_packet(sock.getsockname()[0], address[0], packet_info['dest_port'], packet_info['src_port'], ack_payload)
                    send_ack(sock, ack_packet, address[0], address[1])
                    print(f"Sent ACK for packet {payload_info['seq_no']}")
                else:
                    # log the packet only if its unreliable, let sender handle logging of reliable ones
                    time_received = int(time.time() * 100000) % (2**32) # milliseconds

                    rtt_unreliable = ((time_received - payload_info['timestamp']) % (2**32))
                    
                    csv_row = {
                        'Channel': payload_info['channel_type'],
                        'Packet Number': payload_info['seq_no'],
                        'Time Sent': payload_info['timestamp'],
                        'Time Received': time_received,
                        'RTT Unreliable': rtt_unreliable,
                        'Time ACK Received': 0, # receiver don't know
                        'RTT Reliable': 0 # this one is sender add
                    }

                    write_to_csv_file(args.log, CSV_FIELDNAMES, csv_row) 

    except KeyboardInterrupt:
        print("keyboard interrupt")
        pass
    finally:
        print("stopping receiver")
        # api.stop()
        pass

if __name__ == "__main__":
    main()