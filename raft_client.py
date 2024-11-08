import socket
import json
import sys

def send_command(host: str, port: int, command: dict) -> None:
    """
    Sends a command to a Raft node over a TCP connection.

    Parameters:
        host (str): The IP address or hostname of the target Raft node.
        port (int): The port number of the target Raft node.
        command (dict): A dictionary containing the command to be sent.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
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

def parse_value(value_str: str):
    """
    Attempts to parse the input string into an appropriate Python data type.
    
    Parameters:
        value_str (str): The string to parse
        
    Returns:
        The parsed value in its appropriate type
    """
    try:
        # Try to parse as JSON first (for dicts, lists, etc.)
        return json.loads(value_str)
    except json.JSONDecodeError:
        # If not valid JSON, handle other cases
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        try:
            # Try to convert to number
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            # If all else fails, return as string
            return value_str

def main():
    """
    Parses command-line arguments and sends commands to Raft nodes.
    
    Usage:
        python raft_client.py set_state <key> <value>
        python raft_client.py get_state
        
    Examples:
        # Set string value
        python raft_client.py set_state message "Hello World"
        
        # Set numeric value
        python raft_client.py set_state count 42
        
        # Set boolean value
        python raft_client.py set_state ready true
        
        # Set list value
        python raft_client.py set_state numbers "[1, 2, 3, 4]"
        
        # Set dictionary value
        python raft_client.py set_state config '{"host": "localhost", "port": 8080}'
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python raft_client.py set_state <key> <value>")
        print("  python raft_client.py get_state")
        print("\nExamples:")
        print('  python raft_client.py set_state message "Hello World"')
        print("  python raft_client.py set_state count 42")
        print("  python raft_client.py set_state ready true")
        print('  python raft_client.py set_state numbers "[1, 2, 3, 4]"')
        print('  python raft_client.py set_state config \'{"host": "localhost", "port": 8080}\'')
        return

    command = sys.argv[1]
    ports = [5000, 5001, 5002]

    if command == "set_state":
        if len(sys.argv) < 4:
            print("Usage: python raft_client.py set_state <key> <value>")
            return
            
        key = sys.argv[2]
        value = parse_value(sys.argv[3])
        message = {
            "type": "set_state",
            "value": {key: value}
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