import socket
import json
import sys
import time
import random
from threading import Thread, Lock, Event

class RaftNode:
    def __init__(self, node_id, port):
        self.node_id = node_id
        self.port = port
        self.state = 'follower'
        self.current_term = 0
        self.voted_for = None
        self.state_value = ""
        self.lock = Lock()
        self.shutdown_event = Event()
        self.last_heartbeat = time.time()
        self.votes_received = 0
        self.other_nodes = [(5000 + i) for i in range(3) if (5000 + i) != port]
        
        # Increase timeouts to reduce election conflicts
        self.MIN_TIMEOUT = 2.0  # Increased from 1.0
        self.MAX_TIMEOUT = 4.0  # Increased from 2.0
        self.election_timeout = self.get_random_timeout()
        
        # Initialize socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"Node {self.node_id} initialized on port {self.port}")

    def get_random_timeout(self):
        return random.uniform(self.MIN_TIMEOUT, self.MAX_TIMEOUT)

    def start(self):
        """Start the node"""
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        print(f"Node {self.node_id} listening on port {self.port}")
        
        # Start election timer
        election_thread = Thread(target=self.run_election_timer, daemon=True)
        election_thread.start()
        
        # Start heartbeat sender if leader
        heartbeat_thread = Thread(target=self.send_heartbeats, daemon=True)
        heartbeat_thread.start()
        
        # Accept connections
        while not self.shutdown_event.is_set():
            try:
                self.server_socket.settimeout(1)
                try:
                    client_socket, _ = self.server_socket.accept()
                    Thread(target=self.handle_connection, args=(client_socket,), daemon=True).start()
                except socket.timeout:
                    continue
            except Exception as e:
                if not self.shutdown_event.is_set():
                    print(f"Error accepting connection: {e}")

    def handle_connection(self, client_socket):
        """Handle client connection"""
        try:
            data = client_socket.recv(1024).decode()
            if data:
                message = json.loads(data)
                print(f"Node {self.node_id} received: {message}")  # Debug log
                response = self.handle_message(message)
                if response:
                    client_socket.send(json.dumps(response).encode())
        except Exception as e:
            print(f"Error handling connection: {e}")
        finally:
            client_socket.close()

    def handle_message(self, message):
        """Handle incoming message"""
        msg_type = message.get('type')

        if msg_type == 'set_state':
            return self.handle_set_state(message)
        elif msg_type == 'get_state':
            return self.handle_get_state()
        elif msg_type == 'heartbeat':
            with self.lock:
                leader_id = message.get('leader_id')
                term = message.get('term', 0)
                state_value = message.get('state_value', '')  # Add this line
                
                if term >= self.current_term:
                    was_leader = self.state == 'leader'
                    self.current_term = term
                    self.state = 'follower'
                    self.last_heartbeat = time.time()
                    self.state_value = state_value  # Add this line to sync state
                    if was_leader:
                        print(f"Node {self.node_id} stepping down: received heartbeat from Node {leader_id} with term {term}")
                    return {'term': self.current_term, 'success': True}
            return {'term': self.current_term, 'success': False}
        elif msg_type == 'request_vote':
            with self.lock:
                term = message.get('term', 0)
                candidate_id = message.get('candidate_id')
                
                # If we see a higher term, revert to follower
                if term > self.current_term:
                    self.current_term = term
                    self.state = 'follower'
                    self.voted_for = None
                    self.last_heartbeat = time.time()  # Reset heartbeat timer
                
                # Only grant vote if we haven't voted this term and candidate's term is current
                if (term >= self.current_term and 
                    (self.voted_for is None or self.voted_for == candidate_id)):
                    self.voted_for = candidate_id
                    self.current_term = term
                    self.last_heartbeat = time.time()  # Reset heartbeat timer
                    print(f"Node {self.node_id} voting for Node {candidate_id}")
                    return {'term': self.current_term, 'vote_granted': True}
                
                return {'term': self.current_term, 'vote_granted': False}

    def handle_set_state(self, message):
        """Handle set_state request"""
        with self.lock:
            if self.state != 'leader':
                return {
                    'success': False,
                    'error': 'Not the leader',
                    'leader_port': self.find_current_leader()
                }
            
            new_value = message.get('value', '')
            self.state_value = new_value
            print(f"Node {self.node_id} (Leader) setting state to: {new_value}")
            
            # Propagate state to followers via heartbeats
            # (The state will be sent in the next heartbeat cycle)
            return {'success': True}

    def handle_get_state(self):
        """Handle get_state request"""
        with self.lock:
            return {
                'success': True,
                'state': self.state_value,
                'is_leader': self.state == 'leader'
        }

    def find_current_leader(self):
        """Try to find the current leader's port"""
        # Simple implementation - try to contact other nodes
        for port in [5000, 5001, 5002]:
            if port == self.port:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(('localhost', port))
                    s.send(json.dumps({'type': 'get_state'}).encode())
                    response = json.loads(s.recv(1024).decode())
                    if response.get('is_leader', False):
                        return port
            except:
                continue
        return None

    def run_election_timer(self):
        """Monitor for election timeout"""
        while not self.shutdown_event.is_set():
            time.sleep(0.1)
            
            # First check if we should start election without holding the lock
            should_start_election = False
            current_time = time.time()
            
            with self.lock:
                if self.state != 'leader':
                    time_since_heartbeat = current_time - self.last_heartbeat
                    if time_since_heartbeat > self.election_timeout:
                        should_start_election = True
            
            # Start election outside the lock if needed
            if should_start_election:
                self.start_election()

    def start_election(self):
        """Start a new election"""
        # First acquire lock briefly to update state
        with self.lock:
            if self.state == 'leader':  # Quick check if we're already leader
                return
                
            print(f"Node {self.node_id} starting election")
            self.state = 'candidate'
            self.current_term += 1
            self.voted_for = self.node_id
            self.votes_received = 1  # Vote for self
            current_term = self.current_term  # Store current term for vote requests
            
        print(f"Node {self.node_id} became candidate for term {current_term}")
        
        # Request votes from other nodes without holding the lock
        for port in self.other_nodes:
            try:
                self.request_vote(port, current_term)
            except Exception as e:
                print(f"Error requesting vote from port {port}: {e}")

    def request_vote(self, port, term):
        """Send vote request to another node"""
        request = {
            'type': 'request_vote',
            'term': term,
            'candidate_id': self.node_id
        }
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(('localhost', port))
                s.send(json.dumps(request).encode())
                
                response = json.loads(s.recv(1024).decode())
                print(f"Node {self.node_id} got vote response from port {port}: {response}")
                
                # Handle the vote response
                if response.get('vote_granted', False):
                    self.handle_vote_granted(term)
                elif response.get('term', 0) > term:
                    # Step down if we discover a higher term
                    with self.lock:
                        if response['term'] > self.current_term:
                            self.current_term = response['term']
                            self.state = 'follower'
                            self.voted_for = None
                            self.last_heartbeat = time.time()
                        
        except Exception as e:
            print(f"Error requesting vote from port {port}: {e}")

    def handle_vote_granted(self, term):
        """Handle received vote"""
        with self.lock:
            # Only count the vote if we're still a candidate and in the same term
            if self.state == 'candidate' and self.current_term == term:
                self.votes_received += 1
                print(f"Node {self.node_id} received vote. Total votes: {self.votes_received}")
                
                # Check if we have majority
                if self.votes_received >= 2:  # Majority of 3 nodes
                    self.become_leader()

    def become_leader(self):
        """Transition to leader state"""
        # We already have the lock from handle_vote_granted
        if self.state == 'candidate':  # Double check we're still candidate
            self.state = 'leader'
            self.last_heartbeat = time.time()
            print(f"Node {self.node_id} became leader for term {self.current_term}")
            # Start sending heartbeats immediately
            Thread(target=self.send_initial_heartbeats, daemon=True).start()
            
    def send_initial_heartbeats(self):
        """Send immediate heartbeats upon becoming leader"""
        print(f"Sending initial heartbeats as new leader for term {self.current_term}")
        current_term = self.current_term
        for port in self.other_nodes:
            try:
                self.send_heartbeat(port, current_term)
            except Exception as e:
                print(f"Error sending initial heartbeat to port {port}: {e}")
    
    def send_heartbeats(self):
        """Send heartbeats to other nodes if leader"""
        while not self.shutdown_event.is_set():
            with self.lock:
                is_leader = self.state == 'leader'
                current_term = self.current_term
            
            if is_leader:
                print(f"Leader {self.node_id} sending heartbeats for term {current_term}")
                for port in self.other_nodes:
                    try:
                        self.send_heartbeat(port, current_term)
                    except Exception as e:
                        print(f"Error sending heartbeat to port {port}: {e}")
            
        time.sleep(0.5)  # Wait before next heartbeat round

    def send_heartbeat(self, port, term):
        """Send a single heartbeat to another node"""
        heartbeat = {
            'type': 'heartbeat',
            'term': term,
            'leader_id': self.node_id,
            'state_value': self.state_value  # Add this line to include state in heartbeats
        }
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(('localhost', port))
                s.send(json.dumps(heartbeat).encode())
            
                # Wait for and process response
                data = s.recv(1024).decode()
                if data:  # Only try to parse if we got data
                    response = json.loads(data)
                    
                    # If we discover a higher term, step down
                    if response.get('term', 0) > term:
                        with self.lock:
                            if response['term'] > self.current_term:
                                print(f"Discovered higher term {response['term']} stepping down from leader")
                                self.current_term = response['term']
                                self.state = 'follower'
                                self.voted_for = None
                                self.last_heartbeat = time.time()
                
        except socket.timeout:
            print(f"Heartbeat to port {port} timed out")
        except ConnectionRefusedError:
            print(f"Connection refused for heartbeat to port {port}")
        except json.JSONDecodeError:
            print(f"Invalid response from port {port}")
        except Exception as e:
            print(f"Unexpected error sending heartbeat to port {port}: {e}")

    def shutdown(self):
        """Shutdown the node"""
        self.shutdown_event.set()
        self.server_socket.close()

def main():
    if len(sys.argv) != 2:
        print("Usage: python raft.py <node_id>")
        return

    node_id = int(sys.argv[1])
    port = 5000 + node_id
    
    node = RaftNode(node_id, port)
    
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\nShutting down node {node_id}")
        node.shutdown()

if __name__ == "__main__":
    main()