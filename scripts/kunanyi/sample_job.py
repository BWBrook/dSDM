"""Sample a PBS job shell and all live descendants without extra dependencies."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parent = int(sys.argv[1])
output = Path(sys.argv[2])
with output.open('x') as stream:
    while Path('/proc/%s' % parent).exists():
        rows = subprocess.check_output(['ps', '-eo', 'pid=,ppid=,rss=,pcpu='], universal_newlines=True)
        processes = {}
        for row in rows.splitlines():
            pid, ppid, rss, cpu = row.split()
            processes[int(pid)] = (int(ppid), int(rss) * 1024, float(cpu))
        descendants = {parent}
        while True:
            expanded = descendants | {pid for pid, info in processes.items() if info[0] in descendants}
            if expanded == descendants:
                break
            descendants = expanded
        json.dump({'unix_time': time.time(), 'parent_pid': parent,
                   'rss_bytes': sum(processes[p][1] for p in descendants if p in processes),
                   'cpu_percent': sum(processes[p][2] for p in descendants if p in processes),
                   'pids': sorted(descendants)}, stream)
        stream.write('\n')
        stream.flush()
        time.sleep(5)
