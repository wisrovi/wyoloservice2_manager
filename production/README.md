# WDarwin Ops - Manager Production Deployment

This folder contains the necessary files to deploy the **Manager** and its **Cluster Control Center (UI)** in a production environment, isolating the deployment from the development source code.

## Differences from Development Environment
1. **No `--build`**: Uses pre-built images from Docker Hub (`wisrovi/train_service`) directly.
2. **No code volumes**: The code is already baked into the images, preventing accidental local changes from breaking the production environment.
3. **Constant Restart**: Uses `restart: always` to ensure high availability in case of server reboots.

## How to deploy
1. Review or modify the `control_host.env` file with the correct IPs.
2. Spin up the services by downloading the images from Docker Hub:

```bash
docker compose pull
docker compose up -d
```

3. Access the Cluster Control Center on port 80 of this server.