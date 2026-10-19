# Running the NS2 scenario in the college lab

This guide is for running `ns2/netmind_scenario.tcl` on a lab machine that has NS2 (typically Ubuntu with ns-2.35), then analysing the trace with NetMind on a laptop. Nothing here assumes a particular folder layout on the lab machine: every command runs inside a folder you create yourself.

## Status

| Status | Meaning | State |
| --- | --- | --- |
| **Implemented** | TCL scenario and trace parser reviewed and fixed | Done (2026-10-15) |
| **Validated** | Parser and NetMind pipeline tested on a sample trace | Done, on a **synthetic** sample (`tests/data/sample_ns2.tr`, produced by a Python model, not by NS2) |
| **Executed** | `netmind_scenario.tcl` actually run with NS2 | **Done 2026-10-15** on Ubuntu 24.04 (the team laptop): all 5 checks of `check_trace.py` passed (delay 43.0 ms before the burst, 103.1 ms during it; 0 drops before, 21 during; TCP rerouted via n4 at 115.2 ms). The RED variant (section 9a) has **not been run yet** |

## What the scenario does

| Time | Event | What should appear in the trace |
| --- | --- | --- |
| 0.5 s | TCP (FTP) n0 -> n3 starts, window 6 packets | `tcp` packets n0-n2-n3, no drops |
| 3.0 s | UDP (CBR 0.9 Mb/s) n1 -> n3 starts | queue at n2->n3 fills: `d` lines on link 2 3, delay rises |
| 6.0 s | UDP stops | drops stop, delay returns to normal |
| 7.0 s | link n2-n3 goes down | packets on that link dropped; DV reroutes TCP via n4 (`+ ... 2 4 tcp`) |
| 8.5 s | link n2-n3 back up | TCP returns to n2-n3 |
| 10.0 s | simulation ends | `finish` closes the files and exits |

## 1. What you need

**On the lab machine**
- `ns` (NS2). Required.
- `nam` (Network Animator). Optional, for the animation screenshots.
- `python3`. Optional, for the quick check in step 5. Only the standard library is used; no pip packages are needed.

**On your laptop** (Windows is fine; NS2 is not needed)
- The NetMind repo with its requirements installed (`pip install -r requirements.txt`).

**Files to bring to the lab** (from the repo's `ns2/` folder, by USB, email, or downloading the repo ZIP from GitHub):
- `netmind_scenario.tcl` (required)
- `check_trace.py` (optional, for the quick check)

## 2. Setup checks on the lab machine

Open a terminal and run these one at a time:

```bash
which ns                 # should print a path, e.g. /usr/bin/ns
which nam                # optional; a path means NAM is installed
python3 --version        # optional
lsb_release -a           # note the Ubuntu version for your record
```

Confirm NS2 can run a script (this does not need any of our files):

```bash
mkdir -p ~/netmind_ns2 && cd ~/netmind_ns2
printf 'set ns [new Simulator]\nputs "NS2 works"\nexit 0\n' > ns_check.tcl
ns ns_check.tcl          # expected output: NS2 works
```

If `which ns` prints nothing, see "`ns: command not found`" under Common errors.

## 3. Copy the files into your working folder

Use the `~/netmind_ns2` folder from step 2 (any folder you can write to works). Copy `netmind_scenario.tcl` and `check_trace.py` into it, then check:

```bash
cd ~/netmind_ns2
ls -l                    # netmind_scenario.tcl (and check_trace.py) should be listed
pwd                      # note this path: the output files will be created here
```

If the files came from a Windows laptop, remove Windows line endings first (harmless if there are none):

```bash
sed -i 's/\r$//' netmind_scenario.tcl check_trace.py
```

## 4. Run the simulation

```bash
cd ~/netmind_ns2
ns netmind_scenario.tcl 2>&1 | tee ns_run_output.txt
```

Expected console output (the timing lines come from the script):

```
NetMind NS2 scenario: running 10 s simulation, output base name 'netmind', bottleneck queue DropTail
t= 0.50 s  TCP flow n0 -> n3 starts
t= 3.00 s  UDP burst n1 -> n3 starts (congestion expected)
t= 6.00 s  UDP burst stops
t= 7.00 s  link n2-n3 down (DV should reroute via n4)
t= 8.50 s  link n2-n3 up
Simulation finished at t=10 s
Trace file:     netmind.tr
NAM animation:  netmind.nam   (open with: nam netmind.nam)
```

To keep several runs, give each one its own output name (the first argument after the script):

```bash
ns netmind_scenario.tcl run2       # writes run2.tr and run2.nam
```

### Output files

They are created in the folder you ran `ns` from (the `pwd` in step 3):

| File | What it is |
| --- | --- |
| `netmind.tr` | Trace: one line per packet event. This is what NetMind analyses |
| `netmind.nam` | Animation for NAM |
| `ns_run_output.txt` | The console output saved by `tee` |

Check them:

```bash
ls -lh netmind.tr netmind.nam      # both should exist and not be 0 bytes
head -5 netmind.tr                 # lines like: + 0.5 0 2 tcp 1040 ------- 1 0.0 3.0 0 0
wc -l netmind.tr                   # several thousand lines expected
```

Quick look at the key events with standard tools:

```bash
grep -c '^d' netmind.tr                              # number of drop events (should be > 0)
awk '$1=="d" {print $2, $3, $4, $5}' netmind.tr | head   # time, link (from to), packet type of drops
awk '$1=="+" && $3==2 && $4==4 && $5=="tcp"' netmind.tr | head -3   # TCP using the backup n2->n4
grep -c rtProtoDV netmind.tr                         # Distance Vector routing messages (> 0)
grep -i 'link-' netmind.tr | head                    # link down/up lines, if this NS2 build writes them
```

## 5. Quick check in the lab (no pandas needed)

```bash
python3 check_trace.py netmind.tr | tee check_output.txt
```

It prints per-flow totals, a per-second table, drops per link, route changes, and five scenario checks. A successful run ends with:

```
Scenario checks
  [PASS] no drops before the UDP burst (0.5-3 s)
  [PASS] drops during the UDP burst (3-6 s)
  [PASS] delay higher during the burst than before
  [PASS] traffic rerouted via n4 during the link failure (7-8.5 s)
  [PASS] TCP delay higher on the backup path
```

A FAIL is not necessarily a broken run; see "A scenario check fails" under Common errors. Record it either way.

## 6. Watch the animation (optional, for screenshots)

```bash
nam netmind.nam &
```

Press play and use the time slider. What to look for:

| Time | In NAM |
| --- | --- |
| about 1 s | blue (TCP) packets flowing n0 -> n2 -> n3, no queue |
| about 4 s | red (UDP) packets join; the queue at n2 towards n3 builds up; dropped packets fall off the link |
| about 7.5 s | link n2-n3 shown as down; blue packets go n2 -> n4 -> n3 |
| about 9 s | link back up; packets use n2-n3 again |

## 7. Bring the results back

Copy these files from the lab folder to a USB drive or email them to yourself:

```
netmind.tr   netmind.nam   ns_run_output.txt   check_output.txt   (and your screenshots)
```

On the laptop, put them in the repo in a dated folder, for example:

```
NetMind\ns2\results\2026-10-20\netmind.tr
```

`ns2/results/` is not ignored by git, so these files can be committed as evidence.

## 8. Analyse with NetMind on the laptop

In the VS Code terminal at the repo root (with the virtual environment activated). On Windows use `\` in paths; on Mac/Linux use `/`.

```bash
# full analysis: metrics, anomaly detection, incidents, saved for the dashboard and Copilot
python -m netmind ns2 ns2\results\2026-10-20\netmind.tr --name "NS2 lab run 2026-10-20"

# detailed tables (per flow, per window, links, routes) and a CSV
python ns2\parse_trace.py ns2\results\2026-10-20\netmind.tr --out ns2\results\2026-10-20\metrics.csv

# same quick check as in the lab
python ns2\check_trace.py ns2\results\2026-10-20\netmind.tr

# questions and routing
python -m netmind ask "Why is the network slow, and did any link fail?"
python -m netmind routes --from n0 --to n3 --weight hops

# dashboard: pick the NS2 run in the sidebar
python -m netmind dashboard
```

Options for `python -m netmind ns2`: `--window 0.5` (seconds per window) and `--train-until 3.0` (seconds of normal traffic used as the baseline; keep it before the UDP burst at 3 s).

## 9. How to verify each behaviour

Definitions used by every NetMind tool: a packet is **sent** at its first `+` at its source node, **delivered** at `r` at its destination, **dropped** if it has a `d` and was never delivered. **Loss % = dropped / (delivered + dropped)** for packets sent in the window (packets still in flight at the end are excluded). **Delay** is one-way (receive time - send time). **Jitter** is computed within each flow.

| Behaviour | Where to look | Expected |
| --- | --- | --- |
| Normal period | `check_trace.py` per-second table, 0.5-3 s | 0 drops; delay roughly constant (about 40-45 ms one-way: 10 + 20 ms propagation plus transmission) |
| Congestion | per-second table 3-6 s; `python -m netmind ns2` incidents | drops > 0 on `n2-n3`; loss % clearly above 0; delay much higher than normal (queueing); incident "Network congestion" |
| Packet drops | "Dropped data packets per link" / `parse_trace.py` links table | drops on link `n2-n3`, none on access links |
| Delay changes | per-window `latency_ms`; dashboard latency chart | rises at 3 s, falls after 6 s, rises again at 7 s (longer backup path), falls after 8.5 s |
| Link failure | `grep -i link- netmind.tr` (if present); drops at 7.0 s on `n2 3` | some packets dropped at about 7.0 s; TCP retransmissions in `flow_summary` |
| Rerouting | "Routes" section of `check_trace.py` / `parse_trace.py` | flow 1: `n0-n2-n3`, then `n0-n2-n4-n3` from about 7.0 s, then `n0-n2-n3` again after 8.5 s; incident "Link failure and rerouting" |
| Distance Vector | `grep -c rtProtoDV netmind.tr` | > 0 (routing messages exchanged) |

Exact numbers will differ from the synthetic sample; the pattern is what matters. Write the real numbers into `docs/PROGRESS.md`.

## 9a. Optional: DropTail vs RED on the bottleneck

The script takes an optional second argument, the queue type on the n2-n3 bottleneck: `DropTail` (the default, used above) or `RED` (Random Early Detection). RED drops packets early, at random, once the average queue passes `thresh_` (3 packets here), and always above `maxthresh_` (8), so the queue stays shorter than with DropTail, which only drops when the queue is full.

```bash
cd ~/netmind_ns2
cp ~/NetMind/ns2/compare_traces.py .          # next to check_trace.py (it uses it)
ns netmind_scenario.tcl droptail DropTail     # droptail.tr
ns netmind_scenario.tcl red RED               # red.tr
python3 compare_traces.py droptail.tr red.tr  # phase-by-phase comparison
```

| What to compare | Expected |
| --- | --- |
| Delay during the UDP burst (3-6 s) | Lower with RED (shorter queue) |
| Drops during the burst | Spread over both flows with RED, mostly when the queue is full with DropTail |
| Normal period (0.5-3 s) | Same for both: no drops |
| Link failure (7-8.5 s) | Same rerouting via n4 for both |

Then analyse both in NetMind (`python -m netmind ns2 droptail.tr` and `python -m netmind ns2 red.tr`) and compare them on the dashboard's **Compare runs** page. `check_trace.py red.tr` may report drops before the burst if RED drops early; that check was written for DropTail.

## 10. Common errors and fixes

| Problem | Cause | Fix |
| --- | --- | --- |
| `ns: command not found` | NS2 not installed or not on PATH | Ask the lab admin which command starts NS2. If it was built from source (`ns-allinone-2.35`), add its `bin` folder to PATH, e.g. `export PATH=$PATH:<path-to>/ns-allinone-2.35/bin`. On a machine where you have admin rights: `sudo apt install ns2 nam` |
| `invalid command name ""` or errors mentioning `\r` | Windows line endings in the .tcl file | `sed -i 's/\r$//' netmind_scenario.tcl` and run again |
| `couldn't open "netmind.tr": permission denied` | The folder is not writable (system folder, read-only USB) | `cd ~/netmind_ns2` (a folder in your home) and run there |
| `nam: command not found` | NAM not installed | Skip NAM; the analysis only needs `netmind.tr`. Use another machine for NAM screenshots if needed |
| NAM: `couldn't connect to display` | No graphical session (SSH/terminal only) | Run NAM from the desktop session of the lab machine, or copy `netmind.nam` to a machine with NAM |
| `netmind.tr` is 0 bytes or cut short | Simulation stopped before `finish` ran | Check `ns_run_output.txt` for the error, fix it, rerun; `finish` flushes and closes the files at 10 s |
| Old results overwritten | Same output name used twice | Use a new name: `ns netmind_scenario.tcl run2` |
| Any NS2 error with a line number | Script or NS2 build difference | Save the full message (`ns_run_output.txt`) and bring it back; do not edit the script blindly in the lab |
| `python3: command not found` | Python not installed in the lab | Skip step 5; run the checks on the laptop (step 8) |
| A scenario check fails | e.g. drops before 3 s (TCP alone filled the queue) or no reroute | Record the output. Drops before 3 s: lower `$tcp set window_ 6` to 4. No reroute: confirm the trace has `rtProtoDV` lines and `+ ... 2 4 tcp` lines after 7 s; confirm the `rtproto DV` and `rtmodel-at` lines are in the script |
| `python -m netmind ns2` says "no NS2 packet events found" | Wrong file (e.g. the .nam file) or a wireless/new-format trace | Use the `.tr` file written by `$ns trace-all` |

## 11. Evidence checklist

Screenshots in the lab:
- [ ] Terminal: `which ns` and the `ns ns_check.tcl` output ("NS2 works")
- [ ] Terminal: `ns netmind_scenario.tcl` with all timing lines and "Simulation finished"
- [ ] Terminal: `ls -lh netmind.tr netmind.nam` and `head -5 netmind.tr`
- [ ] Terminal: `python3 check_trace.py netmind.tr` with the five scenario checks
- [ ] NAM at about 1 s (normal), 4 s (queue and drops), 7.5 s (link down, via n4), 9 s (recovered)

Files to bring back:
- [ ] `netmind.tr`, `netmind.nam`, `ns_run_output.txt`, `check_output.txt`

Record (paste into `docs/PROGRESS.md`):
- [ ] Date and time, lab machine or room, Ubuntu version (`lsb_release -a`)
- [ ] NS2 version (if installed with apt: `dpkg -s ns2 | grep Version`)
- [ ] Any errors and how they were fixed

On the laptop:
- [ ] `python -m netmind ns2 ...` report showing both incidents and the route change
- [ ] Dashboard: Traffic & anomalies tab for the NS2 run, Topology tab, a Copilot answer
- [ ] Commit the `ns2/results/<date>/` folder and update the status table at the top of this file: set **Executed** to done, with the date
