# AI Calculability

Docker Compose scaffold for the architecture in `docs/archi.png`.

## Services

| Service | Expected build folder | Browser endpoint |
| --- | --- | --- |
| Angular control panel | `control-panel/` | `http://localhost:4200` |
| Python environment | `environment/` | `http://localhost:8000` |
| Python agent | `agent/` | `http://localhost:8001` |

All three services share the `simulation` bridge network. The agent connects
to the environment's gRPC server at `environment:50051`; this port is not
published to the host. This assumes the environment is the gRPC server and
the agent is its client, which can also support bidirectional streaming.
The control panel is assumed to control both Python services over HTTP.

## Application requirements

Each application folder contains a minimal base-image Dockerfile: Nginx for
the control panel and Python slim for the environment and agent. Application
code and startup commands still need to be added. For now, Nginx serves its
default page and the Python containers exit without starting a service.

- Build the Angular application and copy its static output into Nginx's
  `/usr/share/nginx/html` directory. Nginx listens on port `80` inside its
  container, mapped to port `4200` on the host.
- Python services must read the HTTP/gRPC settings in `compose.yml` and bind
  their servers accordingly. These variables are an application convention,
  not settings that Docker implements automatically.
- The agent must read `ENVIRONMENT_GRPC_ADDRESS` and retry connections while
  the environment starts or restarts.
- Configure Angular's browser-side API URLs as `http://localhost:8000` and
  `http://localhost:8001`. Docker service names only resolve inside the Docker
  network, not in the user's browser. Allow the `http://localhost:4200` origin
  in both Python HTTP APIs' CORS settings.

The host ports bind to loopback for local development.

## Commands

Validate the Compose configuration:

```sh
docker compose config --quiet
```

Build and start the containers:

```sh
docker compose up --build
```

Stop and remove the containers:

```sh
docker compose down
```
