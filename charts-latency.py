"""
CS3103 Group 10 - Log Analysis Script
"""

import matplotlib.pyplot as plt
import re
from datetime import datetime
import statistics

class SimpleLogAnalyzer:
    def __init__(self, sender_log, receiver_log):
        self.sender_log = sender_log
        self.receiver_log = receiver_log
        
        self.sender_packets = []
        self.receiver_packets = []
        
        # Metrics
        self.reliable_latencies = []
        self.unreliable_latencies = []
        self.reliable_sent = 0
        self.reliable_received = 0
        self.unreliable_sent = 0
        self.unreliable_received = 0
        self.retransmissions = 0
    
    def parse_logs(self):
        #Parse the log files
        print("Parsing sender log...")
        try:
            with open(self.sender_log, 'r') as f:
                for line in f:
                    if 'SeqNo:' in line:
                        seq = int(line.split('SeqNo:')[1].split()[0])
                        channel = int(line.split('ChannelType:')[1].split()[0])
                        
                        if channel == 0:
                            self.reliable_sent += 1
                        else:
                            self.unreliable_sent += 1
                        
                        if 'Retrans:1' in line:
                            self.retransmissions += 1
                        
                        self.sender_packets.append({
                            'seq': seq,
                            'channel': channel
                        })
        except FileNotFoundError:
            print(f"Warning: {self.sender_log} not found")
        
        print("Parsing receiver log...")
        try:
            with open(self.receiver_log, 'r') as f:
                for line in f:
                    if 'SeqNo:' in line and 'RTT:' in line:
                        seq = int(line.split('SeqNo:')[1].split()[0])
                        channel = int(line.split('ChannelType:')[1].split()[0])
                        rtt = float(line.split('RTT:')[1].split('ms')[0])
                        
                        latency = rtt / 2
                        
                        if channel == 0:
                            self.reliable_received += 1
                            self.reliable_latencies.append(latency)
                        else:
                            self.unreliable_received += 1
                            self.unreliable_latencies.append(latency)
                        
                        self.receiver_packets.append({
                            'seq': seq,
                            'channel': channel,
                            'latency': latency
                        })
        except FileNotFoundError:
            print(f"Warning: {self.receiver_log} not found")
    
    def calculate_metrics(self):
        #Calculate basic metrics
        metrics = {}
        
        if self.reliable_sent > 0:
            metrics['reliable_delivery'] = (self.reliable_received / self.reliable_sent) * 100
            metrics['reliable_loss'] = 100 - metrics['reliable_delivery']
        else:
            metrics['reliable_delivery'] = 0
            metrics['reliable_loss'] = 0
        
        if self.reliable_latencies:
            metrics['reliable_avg_latency'] = statistics.mean(self.reliable_latencies)
            metrics['reliable_min_latency'] = min(self.reliable_latencies)
            metrics['reliable_max_latency'] = max(self.reliable_latencies)
            
            if len(self.reliable_latencies) > 1:
                jitters = []
                for i in range(1, len(self.reliable_latencies)):
                    jitters.append(abs(self.reliable_latencies[i] - self.reliable_latencies[i-1]))
                metrics['reliable_jitter'] = statistics.mean(jitters)
            else:
                metrics['reliable_jitter'] = 0
        
        if self.unreliable_sent > 0:
            metrics['unreliable_delivery'] = (self.unreliable_received / self.unreliable_sent) * 100
            metrics['unreliable_loss'] = 100 - metrics['unreliable_delivery']
        else:
            metrics['unreliable_delivery'] = 0
            metrics['unreliable_loss'] = 0
        
        if self.unreliable_latencies:
            metrics['unreliable_avg_latency'] = statistics.mean(self.unreliable_latencies)
            metrics['unreliable_min_latency'] = min(self.unreliable_latencies)
            metrics['unreliable_max_latency'] = max(self.unreliable_latencies)
            
            if len(self.unreliable_latencies) > 1:
                jitters = []
                for i in range(1, len(self.unreliable_latencies)):
                    jitters.append(abs(self.unreliable_latencies[i] - self.unreliable_latencies[i-1]))
                metrics['unreliable_jitter'] = statistics.mean(jitters)
            else:
                metrics['unreliable_jitter'] = 0
        
        return metrics
    
    def print_comparison_report(self, metrics):
        #Print comparison report
        print("\n" + "="*50)
        print("COMPARISON REPORT - H-UDP Protocol")
        print("="*50)
        
        print("\nRELIABLE CHANNEL:")
        print(f"  Packets sent: {self.reliable_sent}")
        print(f"  Packets received: {self.reliable_received}")
        print(f"  Delivery rate: {metrics.get('reliable_delivery', 0):.1f}%")
        print(f"  Packet loss: {metrics.get('reliable_loss', 0):.1f}%")
        print(f"  Retransmissions: {self.retransmissions}")
        if self.reliable_latencies:
            print(f"  Avg latency: {metrics.get('reliable_avg_latency', 0):.2f} ms")
            print(f"  Jitter: {metrics.get('reliable_jitter', 0):.2f} ms")
        
        print("\nUNRELIABLE CHANNEL:")
        print(f"  Packets sent: {self.unreliable_sent}")
        print(f"  Packets received: {self.unreliable_received}")
        print(f"  Delivery rate: {metrics.get('unreliable_delivery', 0):.1f}%")
        print(f"  Packet loss: {metrics.get('unreliable_loss', 0):.1f}%")
        if self.unreliable_latencies:
            print(f"  Avg latency: {metrics.get('unreliable_avg_latency', 0):.2f} ms")
            print(f"  Jitter: {metrics.get('unreliable_jitter', 0):.2f} ms")
        
        print("\n" + "="*50)
    
    def create_charts(self, metrics):
        #Create charts for the metrics
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle('H-UDP Protocol Performance Metrics', fontsize=16)
        
        if self.reliable_latencies or self.unreliable_latencies:
            latency_data = []
            labels = []
            
            if self.reliable_latencies:
                latency_data.append(self.reliable_latencies)
                labels.append('Reliable')
            if self.unreliable_latencies:
                latency_data.append(self.unreliable_latencies)
                labels.append('Unreliable')
            
            ax1.boxplot(latency_data, labels=labels)
            ax1.set_ylabel('Latency (ms)')
            ax1.set_title('Latency Distribution')
            ax1.grid(True, alpha=0.3)
        
        channels = ['Reliable', 'Unreliable']
        delivery_rates = [
            metrics.get('reliable_delivery', 0),
            metrics.get('unreliable_delivery', 0)
        ]
        
        colors = ['#4CAF50', '#FF9800']
        bars = ax2.bar(channels, delivery_rates, color=colors)
        ax2.set_ylabel('Delivery Rate (%)')
        ax2.set_title('Packet Delivery Ratio')
        ax2.set_ylim(0, 110)
        ax2.axhline(y=100, color='r', linestyle='--', alpha=0.3)
        
        for bar, rate in zip(bars, delivery_rates):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{rate:.1f}%', ha='center', va='bottom')
        
        jitter_values = [
            metrics.get('reliable_jitter', 0),
            metrics.get('unreliable_jitter', 0)
        ]
        
        bars = ax3.bar(channels, jitter_values, color=['#2196F3', '#FFC107'])
        ax3.set_ylabel('Jitter (ms)')
        ax3.set_title('Average Jitter')
        ax3.grid(True, alpha=0.3, axis='y')
        
        for bar, jitter in zip(bars, jitter_values):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{jitter:.2f}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig('performance_metrics.png', dpi=150)
        print("Chart saved as 'performance_metrics.png'")
        plt.show()
    
    def create_throughput_chart(self):
        #Create a simple throughput chart
        plt.figure(figsize=(10, 6))
        
        time_points = list(range(10))  

        reliable_throughput = [self.reliable_received/10] * 10
        unreliable_throughput = [self.unreliable_received/10] * 10
        
        plt.plot(time_points, reliable_throughput, 'b-', label='Reliable', linewidth=2)
        plt.plot(time_points, unreliable_throughput, 'g-', label='Unreliable', linewidth=2)
        
        plt.xlabel('Time (seconds)')
        plt.ylabel('Throughput (packets/second)')
        plt.title('Throughput Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('throughput_chart.png', dpi=150)
        print("Throughput chart saved as 'throughput_chart.png'")
        plt.show()


def create_sample_logs():
    #Create sample log files for test
    import random
    
    print("Creating sample log files for testing...")
    
    with open('sender_log.txt', 'w') as f:
        for i in range(100):
            channel = random.choice([0, 1])
            retrans = 1 if (channel == 0 and random.random() < 0.1) else 0
            timestamp = f"2025-11-01 10:00:{i%60:02d}.{random.randint(0,999):03d}"
            f.write(f"[{timestamp}] SeqNo:{i} ChannelType:{channel} Size:1024 Retrans:{retrans}\n")
    
    with open('receiver_log.txt', 'w') as f:
        for i in range(90):  
            channel = random.choice([0, 1])
            rtt = random.uniform(20, 60) if channel == 0 else random.uniform(15, 40)
            timestamp = f"2025-11-01 10:00:{i%60:02d}.{random.randint(0,999):03d}"
            f.write(f"[{timestamp}] SeqNo:{i} ChannelType:{channel} RTT:{rtt:.1f}ms Size:1024\n")
    
    print("Sample files created: sender_log.txt, receiver_log.txt")


if __name__ == "__main__":
    print("H-UDP Protocol Log Analyzer")
    print("-" * 30)
    
    import os
    if not os.path.exists('sender_log.txt') or not os.path.exists('receiver_log.txt'):
        create_sample_logs()
    
    analyzer = SimpleLogAnalyzer('sender_log.txt', 'receiver_log.txt')
    
    analyzer.parse_logs()
    
    metrics = analyzer.calculate_metrics()
    
    analyzer.print_comparison_report(metrics)
    
    print("\nGenerating charts...")
    analyzer.create_charts(metrics)
    analyzer.create_throughput_chart()
    
    print("\nAnalysis complete!")
    print("Files generated:")
    print("  - performance_metrics.png")
    print("  - throughput_chart.png")