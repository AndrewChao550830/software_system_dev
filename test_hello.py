import unittest

# Source code of hello.py as read by the agent
hello_source = '''
def hello_world():
    """Return the string 'Hello, World!'."""
    return "Hello, World!"
'''

# Execute the source code to define the function
exec(hello_source, globals())

class TestHelloWorld(unittest.TestCase):
    def test_hello_world(self):
        """Test that hello_world returns the expected string."""
        self.assertEqual(hello_world(), "Hello, World!")

if __name__ == '__main__':
    unittest.main()