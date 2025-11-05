import pickle

class DemoLogger:
  def __init__(self):
    # for sender
    self.sent_seq_no = set() # for seeing total how many packets sent by sender
    self.total_packets_sent_incl_retransmitted = 0
    self.api_total_packets_sent_incl_retransmitted = 0 # total number of packets sent by gamenetapi
    self.api_sent_seq_no = set() # for reliable packets

    # tracks number of retransmissions per packet
    # if packet seq_no not in dictionary, then it was received on the first try
    self.retransmissions = {} 
    self.total_number_of_retransmissions = 0

    # for receiver
    self.received_seq_no = set() # for tracking reliable packets
    self.total_packets_received_incl_retransmitted = 0
    self.duplicates = {}
    self.total_number_of_duplicates_received = 0

    self.api_total_number_unreliable_packets_sent = 0
    self.total_number_unreliable_packets_received = 0


    # for our convenience
    self.print_all_logs = True
    self.print_sender_logs = False
    self.print_receiver_logs = False
    self.print_summary = True

    self.sent_but_not_received_packets = set() # for tracking reliable packets


  
  def log_sent_packet_info(self, seq_no, channel_type, timestamp_sent): # log on packet send from sender.py
    self.track_sent_packet(seq_no)
    if not self.print_all_logs and not self.print_sender_logs:
      return
    print(f"Sender sent {seq_no} through channel {channel_type} at {timestamp_sent}")
    #print(f"{seq_no} has been retransmitted {retransmission_no} times")

  def api_log_sent_packet_info(self, seq_no, channel_type, timestamp_sent): # for gamenetapi, is used in ReliableSender for reliable cases
    self.api_track_sent_packet(seq_no)
    if not self.print_all_logs and not self.print_sender_logs:
      return
    print(f"GameNetAPI sent {seq_no} through channel {channel_type} at {timestamp_sent}")
    print(f"{seq_no} has been retransmitted {self.retransmissions.get(seq_no, 0)} times")


  def api_log_received_packet_info(self, seq_no, channel_type, timestamp_sent, timestamp_received): # log on packet arrival
    self.api_track_received_reliable_packet(seq_no)
    if not self.print_all_logs and not self.print_receiver_logs:
        return
    print(f"Received {seq_no} through channel {channel_type} at {timestamp_received}")
    print(f"{seq_no} was sent at {timestamp_sent}, trip time = {timestamp_received - timestamp_sent}")
    print(f"{seq_no} is duplicate number {self.duplicates.get(seq_no, 0)}")
  
  def print_current_statistics_sender_side(self):
    if not self.print_all_logs and not self.print_summary:
      return
    print(f"Total packets sent = {self.total_packets_sent_incl_retransmitted}")
    
  def api_print_current_statistics_sender_side(self): 
    if not self.print_all_logs and not self.print_summary:
      return
    print(f"GameNetAPI total packets sent = {self.api_total_packets_sent_incl_retransmitted}")
    print(f"GameNetAPI total number of retransmissions = {self.total_number_of_retransmissions}")
    print(f"GameNetAPI total number of unreliable packets sent = {self.api_total_number_unreliable_packets_sent}")
  
  def print_current_statistics_receiver_side(self): 
    if not self.print_all_logs and not self.print_summary:
      return
    print(f"GameNetAPI total packets received = {self.total_packets_received_incl_retransmitted}")
    print(f"GameNetAPI number of duplicates received = {self.total_number_of_duplicates_received}")
    print(f"Number of unreliable packets received = {self.total_number_unreliable_packets_received}")

  def api_log_ack_sent(self, seq_no): # used by ReliableReceiver
    if not self.print_all_logs and not self.print_receiver_logs:
        return
    print(f"ACK sent for {seq_no}")
  
  def api_log_ack_received(self, seq_no, time_received, time_sent, rtt):  # used by ReliableSender
    if not self.print_all_logs and not self.print_sender_logs:
        return
    print(f"ACK received for {seq_no} at {time_received}")
    print(f"RTT for {seq_no} sent at {time_sent} is {rtt}")

  def api_log_sent_unreliable_packet(self):
    self.api_track_sent_unreliable_packet()
    if not self.print_all_logs and not self.print_sender_logs:
      return
    print(f"Sent packet via unreliable channel.")

  def log_received_unreliable_packet(self):
    self.track_unreliable_packet_received()
    if not self.print_all_logs and not self.print_receiver_logs:
      return
    print("Received unreliable packet")


  def track_sent_packet(self, seq_no):
    if seq_no not in self.sent_seq_no:
      self.sent_seq_no.add(seq_no)
    # elif seq_no not in self.retransmissions:
    #   self.retransmissions[seq_no] = 1
    # else:
    #   no_retransmissions = self.retransmissions[seq_no]
    #   self.retransmissions[seq_no] = no_retransmissions + 1
    
    self.total_packets_sent_incl_retransmitted += 1

  def api_track_received_reliable_packet(self, seq_no):
    if seq_no not in self.received_seq_no:
      self.received_seq_no.add(seq_no)
    elif seq_no not in self.duplicates:
      self.duplicates[seq_no] = 1
      self.total_number_of_duplicates_received += 1
    else:
      no_duplicates = self.duplicates[seq_no]
      self.duplicates[seq_no] = no_duplicates + 1
      self.total_number_of_duplicates_received += 1
    
    self.total_packets_received_incl_retransmitted += 1

  def api_track_sent_packet(self, seq_no):
    if seq_no not in self.api_sent_seq_no:
      self.api_sent_seq_no.add(seq_no)
    elif seq_no not in self.retransmissions:
      self.retransmissions[seq_no] = 1
      self.total_number_of_retransmissions += 1
    else:
      no_retransmissions = self.retransmissions[seq_no]
      self.retransmissions[seq_no] = no_retransmissions + 1
      self.total_number_of_retransmissions += 1

    self.api_total_packets_sent_incl_retransmitted += 1

  def api_track_sent_unreliable_packet(self):
    self.api_total_packets_sent_incl_retransmitted += 1
    self.api_total_number_unreliable_packets_sent += 1

  def track_unreliable_packet_received(self):
    self.total_number_unreliable_packets_received += 1



  # use receiver side to find set difference
  def get_set_of_packets_sent_but_not_received(self):
    if len(self.api_sent_seq_no) != 0:
      self.sent_but_not_received_packets = self.api_sent_seq_no - self.received_seq_no
      return True
    else: 
      print("Call method in receiver")
      return False

  def print_sent_but_not_received_packets(self):
    if self.get_set_of_packets_sent_but_not_received():
      print(f"Reliable packets sent but never received = {self.sent_but_not_received_packets}")
    else:
      print("Call method in receiver")

  def serialize_reliable_sent_set(self): # so that receiver can find set difference and log it, call from sender side
    if len(self.api_sent_seq_no) != 0:
      with open('reliable_sent_set.pickle', 'wb') as f:
        pickle.dump(self.api_sent_seq_no, f)

  def read_reliable_sent_set(self): # so that receiver can find set difference and log it
    if len(self.api_sent_seq_no) == 0: 
      with open('reliable_sent_set.pickle', 'rb') as f:
        self.api_sent_seq_no = pickle.load(f)
  




    



