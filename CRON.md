Cron example (runs every 2 hours):

Add the following to your crontab (edit via `crontab -e`):

```
# Run watcher every 2 hours
0 */2 * * * cd /home/jey/projects/webcrawler && /usr/bin/env python -m src.main run >> /var/log/website-watcher.log 2>&1
```

Systemd timer is preferred for nicer integration. See `systemd/` folder for examples.
