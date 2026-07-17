#!/bin/zsh
# Self-contained Thursday finisher: keeps daemon+shipper alive and runs the
# quota-aware supervisor on pending-tail.txt. ChatGPT quota reopens Thu Jul 23;
# supervisor reads resets_at and sleeps in 1h chunks until then, renders the
# tail into hf-stage, the daemon cuts them, the shipper pushes. Fully unattended.
cd ~/Desktop/DriverV2.nosync/vehicle-assets
SP="/private/tmp/claude-501/-Users-razpe-Desktop/32217176-c0e7-4227-b97e-28881e8ea27a/scratchpad"
pkill -f ingest_daemon; pkill -f shipper.py; pkill -f supervisor.sh; sleep 2
nohup tools/ingest_daemon.py --stage "$SP/hf-stage" --idle-exit 900000 > "$SP/daemon.log" 2>&1 &
nohup tools/shipper.py --interval 600 > "$SP/ship.log" 2>&1 &
# supervisor variant: render pending-tail.txt into hf-stage
sed 's|cars-full.txt|pending-tail.txt|g' tools/supervisor.sh |   sed "s|\$SP/stage|\$SP/hf-stage|g; s|SP=\"/private.*|SP=\"$SP\"|" > /tmp/sup-tail.sh
chmod +x /tmp/sup-tail.sh
nohup zsh /tmp/sup-tail.sh > "$SP/supervisor.log" 2>&1 &
echo "tail runner up: daemon+shipper+supervisor on $(grep -c '|' pending-tail.txt) cars"
