# NetMind - NS2 Simulation Module (ns-2.35, wired, standard trace format)
#
# Scenario: normal traffic -> congestion -> link failure with Distance Vector rerouting
#
# Topology:
#
#   n0 (TCP/FTP source) \                     / n3 (sink)
#                         n2 (router) -------
#   n1 (UDP/CBR source) /    \              /
#                             n4 (backup) -/
#
#   n0-n2, n1-n2 : 2 Mb, 10 ms  (access links)
#   n2-n3        : 1 Mb, 20 ms  (bottleneck, main path, queue limit 10 packets)
#   n2-n4, n4-n3 : 1 Mb, 40 ms  (backup path, routing cost 3 per link)
#
# Timeline (10 s):
#   0.5 s  TCP (FTP) n0 -> n3 starts   normal traffic, no drops expected
#   3.0 s  UDP (CBR 0.9 Mb/s) n1 -> n3 congestion on n2-n3: queue fills, drops, delay up
#   6.0 s  UDP stops                   network recovers
#   7.0 s  link n2-n3 goes down        DV reroutes TCP via n2-n4-n3: delay up
#   8.5 s  link n2-n3 comes back up    traffic returns to n2-n3
#   9.5 s  TCP stops, 10.0 s simulation ends
#
# Run:     ns netmind_scenario.tcl            -> netmind.tr, netmind.nam
#          ns netmind_scenario.tcl run2       -> run2.tr, run2.nam  (optional output name)
# Output files are written to the directory you run the command from.

set ns [new Simulator]

# Distance Vector routing (Bellman-Ford) so routes are recomputed when a link fails
$ns rtproto DV

# ---- Output files ----
# Optional first argument: base name for the output files (default "netmind")
if {$argc >= 1} {
    set out [lindex $argv 0]
} else {
    set out "netmind"
}
set tracefile [open $out.tr w]
$ns trace-all $tracefile
set namfile [open $out.nam w]
$ns namtrace-all $namfile

# NAM colours: flow 1 = TCP (blue), flow 2 = UDP (red)
$ns color 1 Blue
$ns color 2 Red

# ---- Nodes ----
set n0 [$ns node]
set n1 [$ns node]
set n2 [$ns node]
set n3 [$ns node]
set n4 [$ns node]
$n0 label "TCP source"
$n1 label "UDP source"
$n2 label "Router"
$n3 label "Sink"
$n4 label "Backup"

# ---- Links ----
$ns duplex-link $n0 $n2 2Mb 10ms DropTail
$ns duplex-link $n1 $n2 2Mb 10ms DropTail
$ns duplex-link $n2 $n3 1Mb 20ms DropTail
$ns duplex-link $n2 $n4 1Mb 40ms DropTail
$ns duplex-link $n4 $n3 1Mb 40ms DropTail

# Routing cost: the main link costs 1 (default); each backup link costs 3,
# so routing prefers n2-n3 and only uses n2-n4-n3 (cost 6) when n2-n3 is down.
$ns cost $n2 $n4 3
$ns cost $n4 $n2 3
$ns cost $n4 $n3 3
$ns cost $n3 $n4 3

# Small queue on the bottleneck so congestion causes visible drops
$ns queue-limit $n2 $n3 10

# NAM layout
$ns duplex-link-op $n0 $n2 orient right-down
$ns duplex-link-op $n1 $n2 orient right-up
$ns duplex-link-op $n2 $n3 orient right
$ns duplex-link-op $n2 $n4 orient right-down
$ns duplex-link-op $n4 $n3 orient right-up
$ns duplex-link-op $n2 $n3 queuePos 0.5

# ---- Flow 1: TCP (Reno-style Agent/TCP) with FTP, n0 -> n3 ----
set tcp [new Agent/TCP]
$tcp set fid_ 1
$tcp set packetSize_ 1000
# Limit the window to 6 packets (about 0.7 Mb/s at this RTT). With the default of 20,
# TCP alone would overflow the 1 Mb bottleneck and drop packets before the UDP burst,
# so the "normal" period would not be normal.
$tcp set window_ 6
$ns attach-agent $n0 $tcp
set sink [new Agent/TCPSink]
$ns attach-agent $n3 $sink
$ns connect $tcp $sink
set ftp [new Application/FTP]
$ftp attach-agent $tcp

# ---- Flow 2: UDP with CBR 0.9 Mb/s, n1 -> n3 (the congestion-causing burst) ----
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
proc note {msg} {
    global ns
    puts [format "t=%5.2f s  %s" [$ns now] $msg]
}

$ns at 0.5 "$ftp start"
$ns at 0.5 "note {TCP flow n0 -> n3 starts}"
$ns at 3.0 "$cbr start"
$ns at 3.0 "note {UDP burst n1 -> n3 starts (congestion expected)}"
$ns at 6.0 "$cbr stop"
$ns at 6.0 "note {UDP burst stops}"
$ns rtmodel-at 7.0 down $n2 $n3
$ns at 7.0 "note {link n2-n3 down (DV should reroute via n4)}"
$ns rtmodel-at 8.5 up $n2 $n3
$ns at 8.5 "note {link n2-n3 up}"
$ns at 9.5 "$ftp stop"
$ns at 10.0 "finish"

proc finish {} {
    global ns tracefile namfile out
    $ns flush-trace
    close $tracefile
    close $namfile
    puts "Simulation finished at t=[$ns now] s"
    puts "Trace file:     $out.tr"
    puts "NAM animation:  $out.nam   (open with: nam $out.nam)"
    exit 0
}

puts "NetMind NS2 scenario: running 10 s simulation, output base name '$out'"
$ns run
