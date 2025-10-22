import csv

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