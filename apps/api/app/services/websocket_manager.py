from typing import List, Dict, Optional
from fastapi import WebSocket

class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Map websocket -> user_id for authenticated connections
        self._user_map: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            self._user_map[websocket] = user_id
    
    def set_user(self, websocket: WebSocket, user_id: int):
        """Associate a user ID with a WebSocket connection."""
        self._user_map[websocket] = user_id
    
    def get_user_id(self, websocket: WebSocket) -> Optional[int]:
        """Get user ID for a WebSocket connection."""
        return self._user_map.get(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self._user_map.pop(websocket, None)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        await websocket.send_json(message)
    
    async def send_to_user(self, user_id: int, message: dict):
        """Send a message to all connections for a specific user."""
        disconnected = []
        for ws, uid in self._user_map.items():
            if uid == user_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_to_authenticated(self, message: dict):
        """Broadcast a message to all authenticated clients."""
        disconnected = []
        for ws in list(self._user_map.keys()):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)
    
    def get_authenticated_user_ids(self) -> List[int]:
        """Get all unique user IDs with active connections."""
        return list(set(self._user_map.values()))
    
    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)

# Global connection manager instance
manager = ConnectionManager()
