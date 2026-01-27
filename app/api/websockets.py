# app/api/websockets.py
"""
WebSocket connection manager for real-time updates.
"""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New client connected via WebSocket.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        # Create a list of connections to iterate over to avoid issues if a client disconnects during broadcast
        connections = list(self.active_connections)
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Could not send message to a WebSocket client: {e}")
                # The disconnect will be handled by the main endpoint's exception handler