"""
Unit tests for subprocess_logger.py module.
"""

import unittest
import unittest.mock
import subprocess
import threading
import time
import logging
import io
from unittest.mock import Mock, MagicMock, patch, call

import sys
import os

from utils.subprocess_logger import SubprocessLogger

class TestSubprocessLogger2(unittest.TestCase):
    def setUp(self):
        pass

    def test(self):
        process = subprocess.Popen('cmd /c echo hello',
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)

        print(process)
        print(type(process))

        #subprocess_logger = SubprocessLogger()
        #subprocess_logger.start()

        print("test")





class TestSubprocessLogger(unittest.TestCase):
    """Test cases for SubprocessLogger class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_process = Mock(spec=subprocess.Popen)
        self.mock_process.stdout = Mock()
        self.mock_process.stderr = Mock()
        self.mock_process.poll.return_value = None  # Process is running
        self.mock_process.wait.return_value = 0  # Successful exit
        
        self.process_name = "test_process"
        
        # Create a logger for testing
        self.test_logger = logging.getLogger(self.process_name)
        self.test_logger.handlers.clear()  # Clear any existing handlers
        
        # Create a string stream to capture log output
        self.log_stream = io.StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
        self.test_logger.addHandler(handler)
        self.test_logger.setLevel(logging.DEBUG)

    def tearDown(self):
        """Clean up after tests"""
        # Clear logger handlers
        self.test_logger.handlers.clear()

    def test_init_basic(self):
        """Test basic initialization of SubprocessLogger"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        self.assertEqual(logger.process, self.mock_process)
        self.assertEqual(logger.process_name, self.process_name)
        self.assertTrue(logger.log_stdout)
        self.assertTrue(logger.log_stderr)
        self.assertFalse(logger.should_stop)
        self.assertIsInstance(logger._stop_event, threading.Event)
        self.assertIsNone(logger.output_parser)
        self.assertIsInstance(logger.logger, logging.Logger)
        self.assertEqual(logger.logger.name, self.process_name)

    def test_init_with_custom_options(self):
        """Test initialization with custom options"""
        mock_parser = Mock()
        logger = SubprocessLogger(
            self.mock_process, 
            self.process_name,
            log_stdout=False,
            log_stderr=False,
            output_parser=mock_parser
        )
        
        self.assertFalse(logger.log_stdout)
        self.assertFalse(logger.log_stderr)
        self.assertEqual(logger.output_parser, mock_parser)

    def test_stop(self):
        """Test stop method sets flags correctly"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        self.assertFalse(logger.should_stop)
        self.assertFalse(logger._stop_event.is_set())
        
        logger.stop()
        
        self.assertTrue(logger.should_stop)
        self.assertTrue(logger._stop_event.is_set())

    def test_log_line_info_level(self):
        """Test _log_line method with INFO level"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        test_line = "Test output line"
        logger._log_line(test_line, "INFO", "stdout")

        # Check that the log was written with correct content
        log_output = self.log_stream.getvalue()
        self.assertIn("[stdout] Test output line", log_output)

    def test_log_line_error_level(self):
        """Test _log_line method with ERROR level"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        test_line = "Error message"
        logger._log_line(test_line, "ERROR", "stderr")

        # Check that the log was written with correct content
        log_output = self.log_stream.getvalue()
        self.assertIn("[stderr] Error message", log_output)

    def test_log_line_with_parser(self):
        """Test _log_line method with output parser"""
        mock_parser = Mock()
        logger = SubprocessLogger(self.mock_process, self.process_name, output_parser=mock_parser)
        
        test_line = "OpenConnect output"
        logger._log_line(test_line, "INFO", "stdout")
        
        # Verify parser was called
        mock_parser.parse_openconnect_output.assert_called_once_with(test_line)

    def test_log_line_with_parser_exception(self):
        """Test _log_line method when parser raises exception"""
        mock_parser = Mock()
        mock_parser.parse_openconnect_output.side_effect = Exception("Parser error")
        logger = SubprocessLogger(self.mock_process, self.process_name, output_parser=mock_parser)
        
        test_line = "OpenConnect output"
        logger._log_line(test_line, "INFO", "stdout")
        
        # Should not raise exception, should log debug message
        log_output = self.log_stream.getvalue()
        self.assertIn("Error parsing output line", log_output)

    def test_monitor_stream_text_mode(self):
        """Test _monitor_stream method with text mode stream"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        # Create a mock text stream
        mock_stream = Mock()
        mock_stream.readline.side_effect = ["Line 1\n", "Line 2\n", ""]  # Empty string ends iteration
        mock_stream.mode = "r"  # Text mode
        
        logger._monitor_stream(mock_stream, "INFO", "stdout")
        
        # Check that lines were logged
        log_output = self.log_stream.getvalue()
        self.assertIn("[stdout] Line 1", log_output)
        self.assertIn("[stdout] Line 2", log_output)
        
        # Verify stream was closed
        mock_stream.close.assert_called_once()

    def test_monitor_stream_binary_mode(self):
        """Test _monitor_stream method with binary mode stream"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        # Create a mock binary stream
        mock_stream = Mock()
        mock_stream.readline.side_effect = [b"Line 1\n", b"Line 2\n", b""]  # Empty bytes ends iteration
        mock_stream.mode = "rb"  # Binary mode
        
        logger._monitor_stream(mock_stream, "INFO", "stdout")
        
        # Check that lines were logged (should be decoded)
        log_output = self.log_stream.getvalue()
        self.assertIn("[stdout] Line 1", log_output)
        self.assertIn("[stdout] Line 2", log_output)

    def test_monitor_stream_with_stop_event(self):
        """Test _monitor_stream method respects stop event"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        logger.should_stop = True
        
        mock_stream = Mock()
        mock_stream.readline.side_effect = ["Line 1\n", "Line 2\n", ""]
        mock_stream.mode = "r"
        
        logger._monitor_stream(mock_stream, "INFO", "stdout")
        
        # Should not log anything because should_stop is True
        log_output = self.log_stream.getvalue()
        self.assertNotIn("[stdout] Line 1", log_output)

    def test_monitor_stream_exception_handling(self):
        """Test _monitor_stream method handles exceptions gracefully"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        mock_stream = Mock()
        mock_stream.readline.side_effect = Exception("Stream error")
        mock_stream.mode = "r"
        
        # Should not raise exception
        logger._monitor_stream(mock_stream, "INFO", "stdout")
        
        # Should log error
        log_output = self.log_stream.getvalue()
        self.assertIn("Error reading from stdout", log_output)

    def test_monitor_stream_empty_lines_filtered(self):
        """Test _monitor_stream method filters out empty lines"""
        logger = SubprocessLogger(self.mock_process, self.process_name)
        
        mock_stream = Mock()
        mock_stream.readline.side_effect = ["Line 1\n", "\n", "   \n", "Line 2\n", ""]
        mock_stream.mode = "r"
        
        logger._monitor_stream(mock_stream, "INFO", "stdout")
        
        log_output = self.log_stream.getvalue()
        self.assertIn("[stdout] Line 1", log_output)
        self.assertIn("[stdout] Line 2", log_output)
        # Empty/whitespace lines should not be logged
        lines = log_output.split('\n')
        stdout_lines = [line for line in lines if "[stdout]" in line]
        self.assertEqual(len(stdout_lines), 2)  # Only 2 non-empty lines


    @patch('threading.Thread')
    def test_run_method_with_stdout_and_stderr(self, mock_thread_class):
        """Test run method creates threads for stdout and stderr monitoring"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Mock thread instances
        mock_stdout_thread = Mock()
        mock_stderr_thread = Mock()
        mock_thread_class.side_effect = [mock_stdout_thread, mock_stderr_thread]

        # Set up process streams
        self.mock_process.stdout = Mock()
        self.mock_process.stderr = Mock()

        logger.run()

        # Verify threads were created and started
        self.assertEqual(mock_thread_class.call_count, 2)
        mock_stdout_thread.start.assert_called_once()
        mock_stderr_thread.start.assert_called_once()

        # Verify process.wait() was called
        self.mock_process.wait.assert_called_once()

        # Verify threads were joined
        mock_stdout_thread.join.assert_called_once_with(timeout=1.0)
        mock_stderr_thread.join.assert_called_once_with(timeout=1.0)

    def test_run_method_stdout_only(self):
        """Test run method with only stdout logging enabled"""
        logger = SubprocessLogger(self.mock_process, self.process_name, log_stderr=False)

        # Set up process streams
        self.mock_process.stdout = Mock()
        self.mock_process.stderr = None

        with patch('threading.Thread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            logger.run()

            # Should only create one thread for stdout
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()

    def test_run_method_stderr_only(self):
        """Test run method with only stderr logging enabled"""
        logger = SubprocessLogger(self.mock_process, self.process_name, log_stdout=False)

        # Set up process streams
        self.mock_process.stdout = None
        self.mock_process.stderr = Mock()

        with patch('threading.Thread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            logger.run()

            # Should only create one thread for stderr
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()

    def test_run_method_no_streams(self):
        """Test run method when no streams are available"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Set up process with no streams
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        with patch('threading.Thread') as mock_thread_class:
            logger.run()

            # Should not create any threads
            mock_thread_class.assert_not_called()

            # Should still wait for process
            self.mock_process.wait.assert_called_once()

    def test_run_method_process_exception(self):
        """Test run method handles process.wait() exception"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Make process.wait() raise an exception
        self.mock_process.wait.side_effect = Exception("Process error")
        self.mock_process.stdout = None
        self.mock_process.stderr = None

        # Should not raise exception
        logger.run()

        # Should log error
        log_output = self.log_stream.getvalue()
        self.assertIn("Error monitoring process", log_output)

    def test_run_method_logs_start_and_completion(self):
        """Test run method logs start and completion messages"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        self.mock_process.stdout = None
        self.mock_process.stderr = None
        self.mock_process.wait.return_value = 0

        logger.run()

        log_output = self.log_stream.getvalue()
        self.assertIn(f"Starting subprocess monitoring for {self.process_name}", log_output)
        self.assertIn(f"Process {self.process_name} finished with return code 0", log_output)
        self.assertIn(f"Subprocess monitoring completed for {self.process_name}", log_output)

    def test_monitor_stream_unicode_decode_error(self):
        """Test _monitor_stream handles unicode decode errors gracefully"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Create a mock binary stream with invalid UTF-8
        mock_stream = Mock()
        mock_stream.readline.side_effect = [b'\xff\xfe\x00\x00invalid\n', b""]
        mock_stream.mode = "rb"

        logger._monitor_stream(mock_stream, "INFO", "stdout")

        # Should not raise exception and should log something (with replacement chars)
        log_output = self.log_stream.getvalue()
        self.assertIn("[stdout]", log_output)

    def test_join_with_timeout_success(self):
        """Test join_with_timeout when thread finishes within timeout"""
        # Note: This test is challenging because the class doesn't actually inherit from Thread
        # We'll test the method logic assuming it should work if the class was properly implemented
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Mock the threading methods that would exist if it inherited from Thread
        with patch.object(logger, 'join') as mock_join, \
             patch.object(logger, 'is_alive', return_value=False) as mock_is_alive:

            result = logger.join_with_timeout(2.0)

            mock_join.assert_called_once_with(timeout=2.0)
            mock_is_alive.assert_called_once()
            self.assertTrue(result)

    def test_join_with_timeout_timeout(self):
        """Test join_with_timeout when thread doesn't finish within timeout"""
        logger = SubprocessLogger(self.mock_process, self.process_name)

        # Mock the threading methods
        with patch.object(logger, 'join') as mock_join, \
             patch.object(logger, 'is_alive', return_value=True) as mock_is_alive:

            result = logger.join_with_timeout(2.0)

            mock_join.assert_called_once_with(timeout=2.0)
            mock_is_alive.assert_called_once()
            self.assertFalse(result)


class TestSubprocessLoggerIntegration(unittest.TestCase):
    """Integration tests for SubprocessLogger"""

    def setUp(self):
        """Set up integration test fixtures"""
        self.process_name = "test_integration"

        # Create a logger for testing
        self.test_logger = logging.getLogger(self.process_name)
        self.test_logger.handlers.clear()

        # Create a string stream to capture log output
        self.log_stream = io.StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setLevel(logging.DEBUG)
        self.test_logger.addHandler(handler)
        self.test_logger.setLevel(logging.DEBUG)

    def tearDown(self):
        """Clean up after integration tests"""
        self.test_logger.handlers.clear()

    def test_real_subprocess_echo(self):
        """Integration test with real subprocess (echo command)"""
        # Create a real subprocess that outputs some text
        process = subprocess.Popen(
            ['echo', 'Hello World'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger = SubprocessLogger(process, self.process_name)

        # Run the logger (this will wait for the process to complete)
        logger.run()

        # Check that output was logged
        log_output = self.log_stream.getvalue()
        self.assertIn("Starting subprocess monitoring", log_output)
        self.assertIn("[stdout] Hello World", log_output)
        self.assertIn("finished with return code 0", log_output)


if __name__ == '__main__':
    unittest.main()
