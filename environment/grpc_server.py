"""gRPC adapter for run state, actions, and opt-in frozen grid access."""

import os

import grpc
from google.protobuf.json_format import ParseDict
from contracts import simulation_pb2 as pb, simulation_pb2_grpc as rpc
from environment.simulation import SimulationError


class EnvironmentService(rpc.EnvironmentServicer):
    def __init__(self, simulation):
        self.sim = simulation

    async def execute(self, context, operation, message):
        async with self.sim.lock:
            try:
                return ParseDict(operation(), message)
            except SimulationError as exc:
                code = {404: grpc.StatusCode.NOT_FOUND, 422: grpc.StatusCode.INVALID_ARGUMENT}.get(
                    exc.status, grpc.StatusCode.FAILED_PRECONDITION)
                await context.abort(code, str(exc))

    async def StartRun(self, request, context):
        return await self.execute(context, lambda: self.sim.start_run(request.request_id), pb.RunState())

    async def Observe(self, request, context):
        def operation():
            self.sim.require_run(request.run_id)
            return self.sim.observe()
        return await self.execute(context, operation, pb.Observation())

    async def ApplyAction(self, request, context):
        action = request.WhichOneof('action')
        return await self.execute(context, lambda: self.sim.apply(
            request.run_id, request.expected_turn, request.action_id,
            (request.move.x, request.move.y) if action == 'move' else None,
            request.stop_reason if action == 'stop_reason' else None), pb.TurnEvent())

    async def GetRunState(self, request, context):
        def operation():
            # Empty ID recovers the latest run after an agent service restart.
            self.sim.require_run(request.run_id or (self.sim.run or {}).get('run_id', ''))
            return self.sim.state()
        return await self.execute(context, operation, pb.RunState())

    async def GetRunGrid(self, request, context):
        def operation():
            self.sim.require_run(request.run_id)
            snapshot = self.sim.run['grid_snapshot']
            return dict(width=snapshot['width'], height=snapshot['height'], walkable_cells=[
                dict(position=dict(x=x, y=y), weight=snapshot['weights'][y][x])
                for y, row in enumerate(snapshot['cells'])
                for x, cell in enumerate(row) if cell != 'obstacle'
            ])
        return await self.execute(context, operation, pb.GridSnapshot())

    async def GetTurnEvents(self, request, context):
        def operation():
            self.sim.require_run(request.run_id)
            return dict(events=[e for e in self.sim.events if e['sequence'] > request.after_sequence])
        return await self.execute(context, operation, pb.Events())

    async def EndRun(self, request, context):
        return await self.execute(context, lambda: self.sim.end(request.run_id), pb.RunState())


async def start_server(simulation):
    server = grpc.aio.server()
    rpc.add_EnvironmentServicer_to_server(EnvironmentService(simulation), server)
    address = f"{os.getenv('GRPC_HOST', '127.0.0.1')}:{os.getenv('GRPC_PORT', '50051')}"
    port = server.add_insecure_port(address)
    if not port:
        raise RuntimeError(f'Cannot bind gRPC server to {address}')
    await server.start()
    return server, port
