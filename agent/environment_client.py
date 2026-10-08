"""Retryable gRPC transport. Action IDs make retries safe."""

import asyncio
import os
from types import MappingProxyType

import grpc
from google.protobuf.json_format import MessageToDict
from contracts import simulation_pb2 as pb, simulation_pb2_grpc as rpc
from agent.models import Move, Neighbor, Observation


def as_dict(message):
    return MessageToDict(message, preserving_proto_field_name=True,
                         always_print_fields_with_no_presence=True)


def observation_from(data):
    def pos(value):
        return value['x'], value['y']
    return Observation(data['run_id'], data['turn'], pos(data['position']), pos(data['goal']),
                       data['current_cell_weight'], MappingProxyType(data['goal_distances']),
                       tuple(Neighbor(pos(n['position']), n['movement_cost'],
                                      MappingProxyType(n['goal_distances'])) for n in data['neighbors']),
                       data['goal_reached'])


class EnvironmentClient:
    def __init__(self, address=None):
        self.channel = grpc.aio.insecure_channel(
            address or os.getenv('ENVIRONMENT_GRPC_ADDRESS', '127.0.0.1:50051'))
        self.stub = rpc.EnvironmentStub(self.channel)

    async def call(self, method, request):
        for attempt in range(3):
            try:
                return as_dict(await method(request, timeout=3))
            except grpc.aio.AioRpcError as exc:
                if exc.code() not in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED) or attempt == 2:
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))

    async def start(self, request_id):
        return await self.call(self.stub.StartRun, pb.StartRequest(request_id=request_id))

    async def apply(self, run_id, turn, action_id, action):
        request = pb.ActionRequest(run_id=run_id, expected_turn=turn, action_id=action_id)
        if isinstance(action, Move):
            request.move.CopyFrom(pb.Position(x=action.target[0], y=action.target[1]))
        else:
            request.stop_reason = action.reason
        return await self.call(self.stub.ApplyAction, request)

    async def end(self, run_id):
        return await self.call(self.stub.EndRun, pb.RunRequest(run_id=run_id))

    async def current(self):
        return await self.call(self.stub.GetRunState, pb.RunRequest())

    async def grid(self, run_id):
        return await self.call(self.stub.GetRunGrid, pb.RunRequest(run_id=run_id))

    async def close(self):
        await self.channel.close()
