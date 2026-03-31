Remote update packages
======================

Component update package:
updates/components/<component>/manifest.json
updates/components/<component>/payload/<files>

Full update package:
updates/full/manifest.json
or
updates/full/<version>/manifest.json

Supported manifest format:
{
  "version": "112_5_patch1",
  "description": "scanner hotfix",
  "restart_app": false,
  "payload_dir": "payload",
  "files": [
    "remote_control/controller.py",
    {"source": "scanner.py", "target": "domain/scanner/engine.py"}
  ]
}

For string entries, source and target paths are the same relative path.
For object entries, source is relative to payload_dir and target is relative to project root.
