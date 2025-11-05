import argparse, socket, time, random
from utilities import make_mock_game_data
from gamenetapi import GameNetAPI
from tools.demologger import DemoLogger

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Receiver host")
    ap.add_argument("--port", type=int, required=True, help="Receiver port")
    ap.add_argument("--duration", type=int, default=30, help="Seconds to run")
    ap.add_argument("--pps", type=int, default=20, help="Packets per second total")
    ap.add_argument("--reliable-ratio", type=float, default=0.5, help="Fraction sent on reliable channel")
    ap.add_argument("--log", default="logs/sender.csv", help="Sender-side transport log")
    ap.add_argument("--verbose", action="store_true", help="Print send/ACK progress")
    ap.add_argument("--print-every", type=int, default=20, help="Print a status line every N sends (when --verbose)")
    #ap.add_argument("--static-t", type=int, default=200, help="If set, forces a static t timeout (ms) instead of adaptive (e.g. 200).")

    args = ap.parse_args()

    demo_logger = DemoLogger()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    api = GameNetAPI(sock, sender_logger=demo_logger, log_path=args.log)
    api.set_peer((args.host, args.port))

    # --- static-t override for testing ---
    #if args.static_t is not None:
    #    static_value = int(args.static_t)
    #    print(f"[CONFIG] Using static t = {static_value} ms for all reliable sends.")
    #    api._compute_dynamic_t = lambda urgency_ms=0: static_value


    sent_total = 0
    sent_rel = 0

    def on_ack(seq: int, rtt_ms: int):
        # Print one-liner per ACK when verbose is on.
        if args.verbose:
            print(f"[ACK] seq={seq} rtt={rtt_ms}ms")

    api.set_callbacks(reliable_cb=None, unreliable_cb=None, ack_cb=on_ack)
    api.start()

    interval = 1.0 / max(1, args.pps)
    end_time = time.time() + args.duration
    i = 0

    try:
        next_send = time.time()
        while time.time() < end_time:
            reliable = (random.random() < args.reliable_ratio)
            payload, timestamp = make_mock_game_data(i)
            api.send(payload, reliable=reliable, urgency_ms=0)
            demo_logger.log_sent_packet_info(i, reliable, timestamp)

            sent_total += 1
            if reliable:
                sent_rel += 1
            if args.verbose and (sent_total % max(1, args.print_every) == 0):
                rel_pct = 100.0 * sent_rel / max(1, sent_total)
                print(f"[SEND] total={sent_total} reliable={sent_rel} ({rel_pct:.1f}%)")

            i += 1
            next_send += interval
            sleep_for = next_send - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_send = time.time()
    finally:
        api.stop()
        demo_logger.serialize_reliable_sent_set()
        demo_logger.print_current_statistics_sender_side()
        demo_logger.api_print_current_statistics_sender_side()
 

if __name__ == "__main__":
    main()

