import logging
import time
import unittest

from log import logger, std_formatter
from ui.task_def import Action
from ui.task_def import State
from ui.event_loop import EventLoop


def print_task(i: int, delay: float = 0):

    def closure(_):
        time.sleep(delay)
        print(f"Task {i}")

        return i + 1

    return closure


def cancel_print_task(i: int):

    def closure(_):
        print(f"Cancel task {i}")

    return closure


def reject_print_task(i: int):

    def closure(_):
        print(f"Active rejection {i}")

    return closure


def print_task_with_exception(i: int):

    def closure(_):
        if i % 4 == 0 :
            raise RuntimeError(f"Passive rejection {i}")
        return i

    return closure


class TestEventLoop(unittest.TestCase):

    FRAME_RATE = int(1 / 144 * 1_0000_0000_0)

    def test_skip_fulfilled(self):
        print("\nTest skip fulfilled")
        loop = EventLoop()
        
        for i in range(8):
            f = print_task(i)
            loop.queue_event(Action[TestEventLoop, int](self, f))

        loop.process(self.FRAME_RATE)

    def test_skip_fulfilled_prev_result(self):
        print("\nTest skip fulfilled prev result")
        loop = EventLoop()

        for i in range(8):
            loop.queue_event(Action[TestEventLoop, None](
                self, lambda x: print(f"Received: {x}")
            ))
            loop.event_actions[-1].prev_result = i

        loop.process(self.FRAME_RATE)

    def test_fulfilled(self):
        print("\nTest fulfilled")
        loop = EventLoop()

        for i in range(8):
            f = print_task(i)
            e = Action[TestEventLoop, int](self, f)
            e.on_result = Action[TestEventLoop, None](
                self, 
                lambda x: print(f"Result: {x}")
            )
            loop.queue_event(e)

        loop.process(self.FRAME_RATE)

    def test_cancel(self):
        print("\nTest cancel")
        loop = EventLoop()

        for i in range(32):
            f = print_task(i)
            e = Action[TestEventLoop, int](self, f)
            if i % 4 == 0:
                e.state = State.cancel
                e.on_cancel = cancel_print_task(i)
            loop.queue_event(e)

        loop.process(self.FRAME_RATE)

    def test_reject(self):
        print("\nTest reject")
        loop = EventLoop()

        for i in range(32):
            f = print_task_with_exception(i)
            e = Action[TestEventLoop, int](self, f)
            if i % 9 == 0:
                e.state = State.reject
                e.on_reject = reject_print_task(i)
            else:
                e.on_result = Action(
                    self,
                    lambda x: print(f"Bypass rejection {x}")
                )
                e.on_reject = lambda err: print(err)

            loop.queue_event(e)

        loop.process(self.FRAME_RATE)

    def test_deadline_exceed(self):
        print("\nTest deadline")
        loop = EventLoop()

        for i in range(4):
            f = print_task(i, delay = 1)
            e = Action[TestEventLoop, int](self, f)
            loop.queue_event(e)

        loop.process(self.FRAME_RATE)

    def test_integration(self):
        print("\nTest integration")

        es: list[Action] = [
            Action[TestEventLoop, None](
                self,
                lambda x: self.assertEqual(x, 0) or print(f"Receiver task (previous) {x}"),
                prev_result = 0
            ),
            Action[TestEventLoop, int](
                self,
                print_task(1),
            ),
            Action[TestEventLoop, int](
                self,
                print_task(2),
                on_result = Action[TestEventLoop, None](
                    self,
                    lambda x: self.assertEqual(x, 3) or print(f"Receivers task {x}")
                )
            ),
            Action[TestEventLoop, int](
                self,
                print_task(4),
                on_result = Action[TestEventLoop, None](
                    self,
                    lambda x: self.assertFalse(True)
                ),
                on_cancel = lambda x: self.assertIsNone(x) or print(f"Active cancellation {x}"),
                state = State.cancel
            ),
        ]
        loop = EventLoop()

        for e in es:
            loop.queue_event(e)

        loop.process(self.FRAME_RATE)


if __name__ == "__main__":
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(std_formatter)
    logger.addHandler(stderr_handler)
    unittest.main()
