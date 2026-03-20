#!/usr/bin/env python3
import asyncio
from riot_web_tools.shell.tty_io import TTYRawIO, TTYActionRaw

class TTYResizeTest:
    event_loop: asyncio.AbstractEventLoop
    tty: TTYRawIO

    def __init__(self) -> None:
        self.event_loop = asyncio.new_event_loop()

        self.tty = TTYRawIO(
            self.__on_tty_raw_input__,
            self.__on_tty_window_resize__,
            event_loop=self.event_loop
        )

    def run(self) -> None:
        self.event_loop.run_forever()

    def __on_tty_raw_input__(self, input: bytes):
        if TTYActionRaw.CANCEL.__bytes__() in input:
            self.event_loop.stop()
            self.tty.close()
        self.tty.write(input)

    def __on_tty_window_resize__(self, rows: int, cols: int) -> None:
        window_mask: str = ""

        cols_spacing: int = int((cols - 2 - len(str(cols))) / 2)
        rows_spacing: int = int((rows - 2 - len(str(rows))) / 2)

        for r in range(rows):
            if (r == 0) or (r + 1 == rows):
                window_mask += ("-" * cols)
                continue
            
            window_mask += "|"
            if r == 1:
                window_mask += (" " * cols_spacing) + str(cols) + (" " * (cols - 2 - len(str(cols)) - cols_spacing))
            elif r > rows_spacing and r < 1 + rows_spacing + len(str(rows)):
                row_label_index: int = r - 1 - rows_spacing
                window_mask += str(rows)[row_label_index] + (" " * (cols - 2 - 1))
            else:
                window_mask += (" " * (cols - 2))
            window_mask += "|"

        self.tty.write(b"\n\r" + window_mask.encode())

import pytest
@pytest.mark.skip(reason="manual test, requires stdio")
def test_tty_io_resize():
    tty_test_term = TTYResizeTest()
    tty_test_term.run()

test_tty_io_resize()