#!/usr/bin/env python3
import asyncio
import websockets.server as wss

pending_websockets: list[wss.WebSocketServerProtocol] = []
open_websockets: dict[int, wss.WebSocketServerProtocol] = {}

def ws_unknown(websocket: wss.WebSocketServerProtocol) -> bool:
    return websocket not in pending_websockets and websocket not in open_websockets.values()

async def on_message(websocket: wss.WebSocketServerProtocol):
    if ws_unknown(websocket):
        print("New Connection")
        pending_websockets.append(websocket)
    
    async for message in websocket:
        if websocket in pending_websockets:
            ws_id: int = int(message)
            open_websockets[ws_id] = websocket
            pending_websockets.remove(websocket)
            print(f"Connection registered with ID={ws_id}")
        
        if websocket in open_websockets.values() and message:
            msgr_id: int = -1
            for id, ws in open_websockets.items():
                if ws == websocket:
                    msgr_id = id
                    break
            if type(message) is bytes:
                msg: str = message.decode()
            elif type(message) is str:
                msg = message
            else:
                raise RuntimeError("msg was weirdly typed!" + str(type(message)))
            if msg:
                print(f"From {msgr_id}:" + msg)
                if msgr_id == 0:
                    for id, ws in open_websockets.items():
                        if id != 0:
                            print(f"Sending from {msgr_id} to {id}:" + msg)
                            await ws.send(msg)
        
async def main():
    async with wss.serve(on_message, "0.0.0.0", 7777) as server:
        await server.serve_forever()

asyncio.run(main())