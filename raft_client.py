import socket
import json
import sys

def send_command(host: str, port: int, command: dict) -> None:
    """Send a command to a Raft node"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)  # Set 2 second timeout
            print(f"Connecting to {host}:{port}...")
            s.connect((host, port))
            
            # Send command
            s.send(json.dumps(command).encode())
            print(f"Command sent: {command}")
            
            # Wait for response
            response = s.recv(1024).decode()
            if response:
                print(f"Response: {response}\n")
            else:
                print("No response received\n")
                
    except ConnectionRefusedError:
        print(f"Connection refused for {host}:{port}\n")
    except socket.timeout:
        print(f"Connection timed out for {host}:{port}\n")
    except Exception as e:
        print(f"Error: {e}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python raft_client.py set_state <value>")
        print("  python raft_client.py get_state")
        return

    command = sys.argv[1]
    ports = [5000, 5001, 5002]

    if command == "set_state":
        if len(sys.argv) < 3:
            print("Usage: python raft_client.py set_state <value>")
            return
            
        value = sys.argv[2]
        message = {
            "type": "set_state",
            "value": value
        }
        
    elif command == "get_state":
        message = {
            "type": "get_state"
        }
        
    else:
        print("Unknown command. Available commands: set_state, get_state")
        return

    # Try each node
    for port in ports:
        send_command("localhost", port, message)
        print("-" * 40)

if __name__ == "__main__":
    main()