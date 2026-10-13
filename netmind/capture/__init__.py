"""M1 Packet Capture

Data acquisition from three sources, all producing the same packet-record
table (see records.py):
  sniffer.py    live capture and pcap reading with Scapy
  ns2.py        NS2 simulation trace files
  synthetic.py  demo traffic with known problems at known times

Owner: Hardik. Phase: 1.
"""
from .records import COLUMNS, to_frame, guess_app

__all__ = ["COLUMNS", "to_frame", "guess_app"]
