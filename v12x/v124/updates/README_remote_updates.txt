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


Telegram upload support in v112_6:
- send a document to the bot from the authorized chat
- worker saves it into updates/full/payload/
- manifest.json is rebuilt automatically
- then run /update_full
- for single-file updates, target path defaults to the same relative file name
