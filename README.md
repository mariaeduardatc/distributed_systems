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

# Get the state
python raft_client.py get_state
```

**Tip:** Change `time.sleep(0.5)` inside `send_heartbeats` for less messages prints on your terminal.

#### All comments and docstrings are mine. They were a way I found to try to show I have an understanding of my code (especially the sections where I used AI more heavily——mentioned bellow)

# Shortcomings
1. The code does not have a log, an important part of building a Raft consensus algorithm. Right now, I directly update the states without saving the past state etc on a log. If there is a disk crash the data would be lost.
2. State updates are sent via heartbeats without acknowledgment. If a follower temporarily misses a heartbeat due to network issues or briefly goes offline, it might miss a state update. When it comes back online, there's no mechanism to detect or recover this missed update since the leader doesn't track which followers have successfully received and applied which updates. If the leader fails immediately after making a change, but before the next heartbeat, that change might be lost entirely, violating the consistency guarantees that Raft is supposed to provide.

# AI Usage Statement
Claude helped me in the following parts of my code:

- **find_current_leader()**: While creating this function I knew I could probably use the information 'get_state' gives me about the leader, but I was not sure how to do it. I gave Claude my functions that handle state for context, and asked how I could use their information to build a function to find the leader. Claude was responsible for the "with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:" section of this part of the code (used this as inspiration for request_vote()).
-  **run_election_timer() and others with lock**: Claude helped me set the locks throughout the code. I was having problems triggering new elections, especially after killing a node. I gave the AI my code and asked for advice on how to solve this problem. After this, I iterated a couple of times through the code to understand what were the sections I need to use locks, and when to hold them (at first I had a lot of deadlock issues).
- **error handling**: After most of my code was done, I asked Calude to iterate through it and refine my error handling.
- **heartbeats**: I struglled to come up with a code to handle the heartbeats (how to create them? send them? acknowledge other nodes' heartbeats?), so I used GPT and Claude to explain it to me and give me the pseudocode for functions that would deal with those cases.
- **raft_client**: Similarly to other cases where I used sockets on the code, Claude helped me come up with the pseudocode for the raft_client. This was a section of the code I relied heavily on the AI since I was completely on the dark on how to build the client mocking.
- **print statements**: I used GPT to go through some of the code and give me some print statements so I could see on my terminal if things where going as planned.
