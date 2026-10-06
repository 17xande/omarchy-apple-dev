# Backlog

Work for when nothing else is open. Remove an entry when it ships or is dropped.

## iOS Simulator on Omarchy Linux

Added 2026-10-06 (lane lead request). Compare the approaches and name the
hardest blocker of each:

- A Darling-style macOS userland compatibility layer that runs CoreSimulator and
  `launchd_sim`. Likely blockers: `launchd_sim`, Metal and IOSurface for
  rendering, and the signed simulator runtimes.
- A macOS VM on an Apple Silicon Linux host that runs the Simulator. Likely
  blocker: Hypervisor access for a macOS guest from Linux.
- Any better route found during the comparison.

Then build the smallest proof for the most promising approach.
