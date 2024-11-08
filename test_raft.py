import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import socket
from raft import RaftNode
from raft_client import parse_value, send_command

class TestRaftClient(unittest.TestCase):
    """Test cases for the Raft client functionality"""
    
    def test_parse_value_string(self):
        """Test parsing of string values"""
        self.assertEqual(parse_value("hello"), "hello")
        self.assertEqual(parse_value("123abc"), "123abc")

    def test_parse_value_numbers(self):
        """Test parsing of numeric values"""
        self.assertEqual(parse_value("123"), 123)
        self.assertEqual(parse_value("123.45"), 123.45)

    def test_parse_value_boolean(self):
        """Test parsing of boolean values"""
        self.assertTrue(parse_value("true"))
        self.assertTrue(parse_value("True"))
        self.assertFalse(parse_value("false"))
        self.assertFalse(parse_value("False"))

    def test_parse_value_json(self):
        """Test parsing of JSON structures"""
        self.assertEqual(parse_value("[1, 2, 3]"), [1, 2, 3])
        self.assertEqual(
            parse_value('{"name": "test", "value": 123}'),
            {"name": "test", "value": 123}
        )

    @patch('socket.socket')
    def test_send_command_success(self, mock_socket):
        """Test successful command sending"""
        # Setup mock
        mock_sock_instance = Mock()
        mock_sock_instance.recv.return_value = json.dumps({"success": True}).encode()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        # Test
        command = {"type": "get_state"}
        send_command("localhost", 5000, command)

        # Verify
        mock_sock_instance.connect.assert_called_once_with(("localhost", 5000))
        mock_sock_instance.send.assert_called_once_with(json.dumps(command).encode())

    @patch('socket.socket')
    def test_send_command_connection_refused(self, mock_socket):
        """Test handling of connection refused error"""
        # Setup mock to raise ConnectionRefusedError
        mock_sock_instance = Mock()
        mock_sock_instance.connect.side_effect = ConnectionRefusedError()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        # Test
        command = {"type": "get_state"}
        send_command("localhost", 5000, command)

        # Verify
        mock_sock_instance.connect.assert_called_once_with(("localhost", 5000))
        mock_sock_instance.send.assert_not_called()

class TestRaftNode(unittest.TestCase):
    """Test cases for the Raft node implementation"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.node = RaftNode(0, 5000)

    def tearDown(self):
        """Clean up after each test method"""
        self.node.shutdown()

    def test_initial_state(self):
        """Test initial state of a new RaftNode"""
        self.assertEqual(self.node.state, 'follower')
        self.assertEqual(self.node.current_term, 0)
        self.assertIsNone(self.node.voted_for)
        self.assertEqual(self.node.state_value, {})
        self.assertEqual(self.node.port, 5000)
        self.assertEqual(self.node.node_id, 0)

    def test_handle_get_state(self):
        """Test get_state message handling"""
        response = self.node.handle_get_state()
        self.assertTrue(response['success'])
        self.assertEqual(response['state'], {})
        self.assertFalse(response['is_leader'])

    def test_handle_set_state_as_follower(self):
        """Test set_state message handling when node is follower"""
        message = {
            'type': 'set_state',
            'value': {'key': 'value'}
        }
        response = self.node.handle_set_state(message)
        self.assertFalse(response['success'])
        self.assertEqual(response['error'], 'Not the leader')

    def test_handle_vote_request_grant(self):
        """Test handling of vote request when vote should be granted"""
        message = {
            'type': 'request_vote',
            'term': 1,
            'candidate_id': 1
        }
        response = self.node.handle_message(message)
        self.assertTrue(response['vote_granted'])
        self.assertEqual(response['term'], 1)
        self.assertEqual(self.node.voted_for, 1)

    def test_handle_vote_request_deny_already_voted(self):
        """Test handling of vote request when node has already voted"""
        # First vote
        self.node.current_term = 1
        self.node.voted_for = 2
        
        # Second vote request in same term
        message = {
            'type': 'request_vote',
            'term': 1,
            'candidate_id': 1
        }
        response = self.node.handle_message(message)
        self.assertFalse(response['vote_granted'])

    def test_handle_heartbeat_valid(self):
        """Test handling of valid heartbeat message"""
        message = {
            'type': 'heartbeat',
            'term': 1,
            'leader_id': 1,
            'state_value': {'key': 'value'}
        }
        response = self.node.handle_message(message)
        self.assertTrue(response['success'])
        self.assertEqual(response['term'], 1)
        self.assertEqual(self.node.state, 'follower')
        self.assertEqual(self.node.state_value, {'key': 'value'})
    
    def test_state_update_through_heartbeat(self):
        """Test state updates received through heartbeat messages"""
        # Initial state update through heartbeat
        heartbeat1 = {
            'type': 'heartbeat',
            'term': 1,
            'leader_id': 1,
            'state_value': {'key1': 'value1'}
        }
        self.node.handle_message(heartbeat1)

        # Verify state was updated
        response1 = self.node.handle_get_state()
        self.assertEqual(response1['state'], {'key1': 'value1'})

        # Second state update through heartbeat
        heartbeat2 = {
            'type': 'heartbeat',
            'term': 1,
            'leader_id': 1,
            'state_value': {'key1': 'value1', 'key2': 'value2'}
        }
        self.node.handle_message(heartbeat2)

        response2 = self.node.handle_get_state()
        self.assertEqual(response2['state'], {
            'key1': 'value1',
            'key2': 'value2'
        })

    def test_state_persistence_after_leader_change(self):
        """Test that state persists when leadership changes"""
        # Set initial state as leader
        self.node.state = 'leader'
        self.node.current_term = 1
        
        set_message = {
            'type': 'set_state',
            'value': {'persistent_key': 'persistent_value'}
        }
        self.node.handle_set_state(set_message)

        # Simulate leadership change through higher term heartbeat
        heartbeat = {
            'type': 'heartbeat',
            'term': 2,
            'leader_id': 2,
            'state_value': self.node.state_value  # New leader sends same state
        }
        self.node.handle_message(heartbeat)

        # Verify state persisted
        get_response = self.node.handle_get_state()
        self.assertEqual(get_response['state'], {'persistent_key': 'persistent_value'})
        self.assertEqual(self.node.state, 'follower')  # Verify node stepped down
        self.assertEqual(self.node.current_term, 2)  # Verify term was updated

if __name__ == '__main__':
    unittest.main()