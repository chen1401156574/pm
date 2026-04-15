# Scripts

Cross-platform helper scripts for running the local Dockerized app.

## Files

- `start-linux.sh`: build and start the stack in detached mode.
- `stop-linux.sh`: stop and remove the stack.
- `start-mac.sh`: build and start the stack in detached mode.
- `stop-mac.sh`: stop and remove the stack.
- `start-windows.ps1`: build and start the stack in detached mode.
- `stop-windows.ps1`: stop and remove the stack.

## Behavior

All start scripts run:

```bash
docker compose up --build -d
```

All stop scripts run:

```bash
docker compose down
```
