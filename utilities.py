import csv
import json
import random
import struct
import time


CSV_FIELDNAMES = ['Channel', 'Packet Number', 'Time Sent', 'Time Received', 'RTT Unreliable', 'Time ACK Received', 'RTT Reliable']

def overwrite_csv_file(file, fieldnames, rows):
    with open(file, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_to_csv_file(file, fieldnames, row):
    with open(file, 'a', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writerow(row)
        csv_file.flush()

def make_flags_byte(channel_type, latency):
    # 1-bit channel_type, 1-bit latency; packed in low bits.
    return (latency << 1) | channel_type

def make_custom_header(flags, seq_no, timestamp):
    # flags:1B, seq:2B, ts:4B (big-endian).
    return struct.pack('!BHI', flags, seq_no, timestamp)

def make_payload(custom_header, mock_game_data):
    return custom_header + mock_game_data

def make_mock_game_data(i):
    obj = {"i": i, "ts": (int(time.time()*1000) % (2**32)), "x": random.random(), "y": random.random()}
    return json.dumps(obj).encode("utf-8"), obj["ts"]
