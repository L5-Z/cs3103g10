import argparse, socket, time, random, struct, select
from header import *
from utilities import *
from gamenetapi import start, stop, send, stats, set_callbacks, set_peer
# from hudp.api import GameNetAPI

WINDOW_SIZE = 5
ACK_TIMEOUT = 20000 # 20000/100 ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Receiver host")
    ap.add_argument("--port", type=int, required=True, help="Receiver port")
    ap.add_argument("--duration", type=int, default=3000, help="Seconds to run")
    ap.add_argument("--pps", type=int, default=40, help="Packets per second total")
    ap.add_argument("--reliable-ratio", type=float, default=0.5, help="Fraction sent on reliable channel")
    ap.add_argument("--log", default="logs/session.csv", help="Receiver will write logs; sender logs a few TX events")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    peer = (args.host, args.port)
    # api = GameNetAPI(sock, peer, log_path=args.log)
    # api.start()
        
    acked_packets = set()
    packet_buffer = {} # buffer for packets in sliding window
    packet_timers = {}
    send_base = 0 # base packet number of sliding window
    next_seq_no = 0 # seq_no of next packet to be sent
    last_send_time = 0


    total = args.duration * args.pps
    interval = 1.0 / max(1, args.pps)
    next_seq_no = 0
    start = int(time.time() * 100000) % (2**32)
    try:
        while next_seq_no < total and (((int(time.time() * 100000) % (2**32)) - start) % (2**32)) < args.duration + 1 or len(packet_buffer) != 0:
            ready, _, _ = select.select([sock], [], [], 0)
            if ready:
                response, address = sock.recvfrom(2048)

                # check if response is an ACK packet, and seq_no of the packet it is ACKing
                packet_info = unpack_packet(response)

                if validate_checksum(address[0], sock.getsockname()[0], packet_info['udp_header'], packet_info['payload']): # only accept if checksum is valid
                    seq_no_of_packet_acked = struct.unpack('!H', packet_info['payload'])[0]
                    
                    if seq_no_of_packet_acked not in acked_packets:
                        acked_packets.add(seq_no_of_packet_acked) # add packet seq no to set of acked packets
                        print(f"ACK received for packet {seq_no_of_packet_acked}")

                        time_ack_received = int(time.time() * 100000) % (2**32)
                    
                        rtt_reliable = (time_ack_received - packet_timers.get(seq_no_of_packet_acked, 0)) % (2**32)
                        
                        row = {
                            'Channel': 0, # bcos only reliable got ACK
                            'Packet Number': seq_no_of_packet_acked,
                            'Time Sent': packet_timers.get(seq_no_of_packet_acked, 0),
                            'Time Received': 'Unknown', # dk when receiver received the original packet
                            'RTT Unreliable': 'NA', # not applicable
                            'Time ACK Received': time_ack_received,
                            'RTT Reliable': rtt_reliable
                        }

                        write_to_csv_file(args.log, CSV_FIELDNAMES, row) # only write reliable packets

                        # remove packet from buffer and timer, and shift the window if possible
                        packet_buffer.pop(seq_no_of_packet_acked, None)
                        packet_timers.pop(seq_no_of_packet_acked, None)

                        # slide the window if can
                        if seq_no_of_packet_acked == send_base:
                            send_base += 1

                else:
                    print(f"invalid checksum for ACK packet number {packet_info['payload']}")

            if len(packet_buffer) == 0:
                send_base += WINDOW_SIZE
            # check if its time for retransmission of any packets
            for packet_number, send_time in packet_timers.items():
                if (int(time.time() * 100000) % (2**32)) - send_time > ACK_TIMEOUT:
                    # retransmit if timeout reached and ack not yet received
                    packet_to_retransmit = bytearray(packet_buffer[packet_number])
                    new_timestamp = int(time.time() * 100000) % (2**32)
                    packet_to_retransmit[3:7] = struct.pack('!I', new_timestamp) # change the timestamp
                    sock.sendto(packet_to_retransmit, peer) # retransmit the packet
                    print(f"retransmitted packet {packet_number}")
                    packet_buffer[packet_number] = packet_to_retransmit # update the packet 
                    packet_timers[packet_number] = new_timestamp # update the timer in the list of timers



            # check if can send next packet
            if (next_seq_no < send_base + WINDOW_SIZE) and ((int(time.time() * 100000) % (2**32)) - last_send_time >= interval) and next_seq_no < total and (((int(time.time() * 100000) % (2**32)) - start) % (2**32)) < args.duration + 1:
                reliable = (random.random() < args.reliable_ratio)
                # urgency_ms = 40 if reliable and (random.random() < 0.2) else 0  # 20% marked a bit urgent
                channel_type = 0 if reliable else 1
                latency = 1 if reliable else 0
                

                # make the payload
                flags = make_flags_byte(channel_type, latency)
                last_send_time = int(time.time() * 100000) % (2**32)
                custom_header = make_custom_header(flags, next_seq_no, last_send_time)
                mock_game_data = make_mock_game_data(next_seq_no)
                payload = make_payload(custom_header, mock_game_data)

                # make the packet
                next_packet = make_packet(sock.getsockname()[0], peer[0], sock.getsockname()[1], peer[1], payload)

                # send the packet
                # for testing, send directly to receiver first
                sock.sendto(next_packet, peer)
                print(f"sent packet {next_seq_no} via {reliable}")
                if not reliable:
                    acked_packets.add(next_seq_no) # just assume packet is already acked if it is not meant to be reliable
                    
                else:
                    # only add reliable packets to buffer and timer
                    packet_buffer[next_seq_no] = next_packet
                    packet_timers[next_seq_no] = last_send_time
                # api.send(mk_payload(i), reliable=reliable, urgency_ms=urgency_ms)
                
                next_seq_no += 1
                
    finally:
        # api.stop()
        print("stopping sender")
        print(f"packets in buffer: {packet_buffer}")
        print(f"packet timers: {packet_timers}")
        pass

if __name__ == "__main__":
    main()