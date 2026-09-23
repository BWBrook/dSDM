"""Sample a Linux PBS shell and live descendants from procfs, without ps formatting."""
import json
import os
from pathlib import Path
import sys
import time


def processes(proc=Path('/proc')):
    result = {}
    ticks = os.sysconf('SC_CLK_TCK')
    pages = os.sysconf('SC_PAGE_SIZE')
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            # comm may contain spaces and parentheses; fields after the LAST
            # closing parenthesis start with state (field 3).
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            result[int(entry.name)] = (int(fields[1]), int(fields[21]) * pages,
                                      (int(fields[11]) + int(fields[12])) / ticks,
                                      fields[19])
        except (OSError, ValueError, IndexError):
            # A process may exit during this non-atomic system snapshot.
            continue
    return result


def main():
    parent = int(sys.argv[1])
    previous = {}
    previous_time = time.monotonic()
    with Path(sys.argv[2]).open('x') as stream:
        while Path('/proc/%s' % parent).exists():
            snapshot = processes()
            now = time.monotonic()
            descendants = {parent}
            while True:
                expanded = descendants | {pid for pid, info in snapshot.items() if info[0] in descendants}
                if expanded == descendants:
                    break
                descendants = expanded
            current = {pid: snapshot[pid] for pid in descendants if pid in snapshot}
            delta = sum(max(0, info[2] - previous[pid][2]) for pid, info in current.items()
                        if pid in previous and info[3] == previous[pid][3])
            json.dump({'unix_time': time.time(), 'parent_pid': parent,
                       'rss_bytes': sum(info[1] for info in current.values()),
                       'cpu_percent': 100 * delta / max(now - previous_time, 1e-9),
                       'cpu_measurement': 'interval_live_processes',
                       'pids': sorted(current)}, stream)
            stream.write('\n')
            stream.flush()
            previous, previous_time = current, now
            time.sleep(5)


if __name__ == '__main__':
    main()
