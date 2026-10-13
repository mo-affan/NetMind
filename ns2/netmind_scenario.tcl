# NetMind - NS2 Simulation Module
# Scenario: normal traffic -> congestion -> link failure with Distance Vector rerouting
#
# Topology:
#
#   n0 (TCP/FTP source) \                    / n3 (sink)
#                         n2 (router) ------
#   n1 (UDP/CBR source) /    \             /
#                             n4 (backup) /
#
#   n2-n3 : 1 Mb, 20 ms   (bottleneck, main path)
#   n2-n4-n3 : 1 Mb, 40 ms each (longer backup path)
#
# Timeline (10 seconds):
#   0.5 s  TCP (FTP) starts            -> normal traffic
#   3.0 s  UDP (CBR) burst starts      -> congestion on n2-n3: queue fills, packets dropped
#   6.0 s  UDP burst stops             -> network recovers
#   7.0 s  link n2-n3 goes down        -> Distance Vector reroutes via n4 (higher delay)
#   8.5 s  link n2-n3 comes back up
#
# Run:   ns netmind_scenario.tcl
# Output: netmind.tr (trace file for NetMind) and netmind.nam (animation, opens in NAM)

set ns [new Simulator]

# Distance Vector routing so the network can reroute around the failed link
$ns rtproto DV

# Colours for NAM: flow 1 = TCP (blue), flow 2 = UDP (red)
$ns color 1 Blue
$ns color 2 Red

# Output files
set tracefile [open netmind.tr w]
$ns trace-all $tracefile
set namfile [open netmind.nam w]
$ns namtrace-all $namfile

# ---- Nodes ----
set n0 [$ns node]
set n1 [$ns node]
set n2 [$ns node]
set n3 [$ns node]
set n4 [$ns node]

# ---- Links ----
$ns duplex-link $n0 $n2 2Mb 10ms DropTail
$ns duplex-link $n1 $n2 2Mb 10ms DropTail
$ns duplex-link $n2 $n3 1Mb 20ms DropTail
$ns duplex-link $n2 $n4 1Mb 40ms DropTail
$ns duplex-link $n4 $n3 1Mb 40ms DropTail

# Prefer the short path n2-n3: give the backup links a higher routing cost
$ns cost $n2 $n4 3
$ns cost $n4 $n2 3
$ns cost $n4 $n3 3
$ns cost $n3 $n4 3

# Small queue on the bottleneck so congestion causes drops
$ns queue-limit $n2 $n3 10

# NAM layout
$ns duplex-link-op $n0 $n2 orient right-down
$ns duplex-link-op $n1 $n2 orient right-up
$ns duplex-link-op $n2 $n3 orient right
$ns duplex-link-op $n2 $n4 orient right-down
$ns duplex-link-op $n4 $n3 orient right-up
$ns duplex-link-op $n2 $n3 queuePos 0.5

# ---- Flow 1: TCP with FTP, n0 -> n3 ----
set tcp [new Agent/TCP]
$tcp set fid_ 1
$tcp set packetSize_ 1000
$ns attach-agent $n0 $tcp
set sink [new Agent/TCPSink]
$ns attach-agent $n3 $sink
$ns connect $tcp $sink
set ftp [new Application/FTP]
$ftp attach-agent $tcp

# ---- Flow 2: UDP with CBR, n1 -> n3 (the congestion-causing burst) ----
set udp [new Agent/UDP]
$udp set fid_ 2
$ns attach-agent $n1 $udp
set null [new Agent/Null]
$ns attach-agent $n3 $null
$ns connect $udp $null
set cbr [new Application/Traffic/CBR]
$cbr set packetSize_ 1000
$cbr set rate_ 0.9Mb
$cbr attach-agent $udp

# ---- Events ----
$ns at 0.5 "$ftp start"
$ns at 3.0 "$cbr start"
$ns at 6.0 "$cbr stop"
$ns rtmodel-at 7.0 down $n2 $n3
$ns rtmodel-at 8.5 up $n2 $n3
$ns at 9.5 "$ftp stop"
$ns at 10.0 "finish"

proc finish {} {
    global ns tracefile namfile
    $ns flush-trace
    close $tracefile
    close $namfile
    puts "Simulation done. Trace: netmind.tr   Animation: netmind.nam"
    exit 0
}

$ns run
