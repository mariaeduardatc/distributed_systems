# Distributed Systems - Raft Protocol

To run the code follow the next commands:
```
# Terminal 1
python raft.py 0  # Uses port 5000

# Terminal 2
python raft.py 1  # Uses port 5001

# Terminal 3
python raft.py 2  # Uses port 5002
```

To change/check the state of the node:
```
# Set a string
python raft_client.py set_state message "Hello World"

# Set a number
python raft_client.py set_state count 42

# Set a boolean
python raft_client.py set_state ready true

# Set a list
python raft_client.py set_state numbers "[1, 2, 3, 4]"

# Set a dictionary
python raft_client.py set_state config '{"host": "localhost", "port": 8080}'

# Set a nested structure
python raft_client.py set_state generals '{"general1": {"ready": true, "troops": 100}, "general2": {"ready": false, "troops": 50}}'

# Get the state
python raft_client.py get_state
```
