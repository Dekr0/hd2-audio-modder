import asyncio
import logging
import time
from typing import Any
import unittest

from log import logger, std_formatter
from ui.task_def import Action 
from ui.task_def import State
from ui.event_loop import EventLoop


def expect(i):

    def closure():
        return i

    return closure


def print_task(i: int, long_task: bool):

    def closure(_):
        if long_task:
            sum = 0
            for r in range(1000000):
                sum += r

        print(f"Task {i}")

        return i + 1

    return closure


def cancel_print_task(i: int, long_task: bool):

    def closure(_):
        if long_task:
            sum = 0
            for r in range(1000000):
                sum += r

        print(f"Cancel task {i}")

    return closure


def micro_task(i: int):

    def closure(_):
        sum = 0
        for r in range(i * 60):
            sum += r

        print(f"Task {i}")

        return sum

    return closure


def micro_task_might_fail(i: int):

    def closure(_):
        sum = 0
        for r in range(i * 5000):
            sum += r
        print(f"Task {i}")
        return sum

    return closure


class TestEventLoop(unittest.TestCase):

    FRAME_RATE = int(1 / 144 * 1_0000_0000_0)

    def test_previous_fulfilled_within_deadline(self):
        print("\ntest_previous_fulfilled_within_deadline")

        loop = EventLoop()

        for i in range(8):
            loop.queue_micro_action(Action[TestEventLoop, None](
                self, lambda x: print(f"Receiving prev task {x}"), prev_result = i,
            ))

        self.assertTrue(loop.process(self.FRAME_RATE))

    def test_previous_fulfilled_exceed_deadline(self):
        print("\ntest_previous_fulfilled_exceeds")
        loop = EventLoop()
        for i in range(8):
            f = print_task(i, i % 4 == 0)
            loop.queue_micro_action(Action[TestEventLoop, Any](
                self, f, prev_result = i
            ))

        self.assertFalse(loop.process(self.FRAME_RATE))
        self.assertFalse(loop.process(self.FRAME_RATE))

    def test_previous_fulfilled(self):
        print("\ntest_previous_fulfilled")
        loop = EventLoop()
        for i in range(40):
            f = print_task(i, i % 5 == 0) 
            loop.queue_micro_action(Action[TestEventLoop, Any](self, f))

        cnt = 8
        while cnt > 0:
            loop.process(self.FRAME_RATE)
            cnt -= 1

    def test_fulfilled_within_deadline(self):
        print("\ntest_fulfilled_within_deadline")
        loop = EventLoop()
        for i in range(40):
            loop.queue_micro_action(Action[TestEventLoop, Any](
                self, micro_task(i),
                on_result=Action[TestEventLoop, Any](
                    self, lambda x: print(f"Received {x}")
                )
            ))
        self.assertTrue(loop.process(self.FRAME_RATE))

    def test_fulfilled_with_deadline_exceed(self):
        print("\ntest_fulfilled_with_deadline_exceed")
        loop = EventLoop()
        for i in range(40):
            loop.queue_micro_action(Action[TestEventLoop, Any](
                self, micro_task_might_fail(i),
                on_result=Action[TestEventLoop, Any](
                    self, lambda x: print(f"Received {x}")
                )
            ))
        cnt = 0
        while cnt < 50:
            if loop.process(self.FRAME_RATE):
                cnt += 1

    def test_cancel_within_deadline(self):
        print("\ntest_cancel_within_deadline")
        loop = EventLoop()
        for i in range(8):
            loop.queue_micro_action(Action[TestEventLoop, Any](
                self, lambda x: print(f"Received {x}"),
                on_cancel = cancel_print_task(i, False),
                state = State.cancel,
                prev_result = i
            ))
        loop.process(self.FRAME_RATE)

    def test_cancel_exceed_deadline(self):
        print("\ntest_cancel_exceed_deadline")
        loop = EventLoop()
        for i in range(8):
            loop.queue_micro_action(Action[TestEventLoop, Any](
                self, lambda x: print(f"Received {x}"),
                on_cancel = cancel_print_task(i, i % 4 == 0),
                state = State.cancel,
                prev_result = i
            ))
        self.assertFalse(loop.process(self.FRAME_RATE))
        self.assertFalse(loop.process(self.FRAME_RATE))


if __name__ == "__main__":
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(std_formatter)
    logger.addHandler(stderr_handler)
    unittest.main()
