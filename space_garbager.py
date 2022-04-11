import asyncio
import curses
import os
from itertools import cycle
from random import randint, choice, random
from time import time, sleep

from curses_tools import draw_frame, read_controls, get_frame_size

TIC_TIMEOUT = 0.08
COUNT_STARS = 200
ROCKET_SPEED = 2
BULLET_SPEED = 2.5


async def blink(canvas, row, column, symbol='*'):
    timing = [2.0, 0.3, 0.5, 0.3]
    nexttime = time() + round(random() * 3, 1)
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        nexttime += timing[0]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol)
        nexttime += timing[1]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol, curses.A_BOLD)
        nexttime += timing[2]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol)
        nexttime += timing[3]
        while time() < nexttime:
            await asyncio.sleep(0)


async def fire(canvas, start_row, start_column, rows_speed=-BULLET_SPEED, columns_speed=0):
    """Display animation of gun shot, direction and speed can be specified."""
    row, column = start_row, start_column
    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')
    row += rows_speed
    column += columns_speed
    symbol = '-' if columns_speed else '|'
    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1
    curses.beep()
    while 1 < row < max_row and 1 < column < max_column:
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


async def fly_rocket(canvas, position, frames):
    frame_gen = cycle(frames)
    for frame in frame_gen:
        frame_position = position.copy()
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, False)
        await asyncio.sleep(0)
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, True)


def load_frames(filelist):
    frames = []
    for file in filelist:
        with open(os.path.join('files', file), 'r') as frame:
            frames.append(str(frame.read()))
    return frames


def get_max_sizes(frames):
    transposed_sizes = list(zip(*[get_frame_size(frame) for frame in frames]))
    return max(transposed_sizes[0]), max(transposed_sizes[1])


def draw(canvas):
    curses.curs_set(False)
    canvas.nodelay(True)
    canvas.border()
    max_row, max_col = canvas.getmaxyx()
    max_row, max_col = max_row - 1, max_col - 1
    canvas.addstr(max_row, 2, f' max_row={max_row}, max_col={max_col} ')
    unic_points = set()
    coroutines = []
    while len(unic_points) < COUNT_STARS:
        star_row, star_col = randint(1, max_row - 1), randint(1, max_col - 1)
        if (star_row, star_col) not in unic_points:
            coroutines.append(blink(canvas, star_row, star_col, symbol=choice(list('+*.:'))))
            unic_points.add((star_row, star_col))
    rocket_frames = load_frames(['rocket_frame_1.txt', 'rocket_frame_2.txt'])
    rocket_height, rocket_width = get_max_sizes(rocket_frames)
    rocket_pos = {'row': (max_row - rocket_height) // 2,
                  'col': (max_col - rocket_width) // 2
                  }
    coroutines.append(fly_rocket(canvas, rocket_pos, rocket_frames))
    fps_time = time()
    while True:
        for cor in coroutines.copy():
            try:
                cor.send(None)
            except StopIteration:
                coroutines.remove(cor)
        canvas.addstr(max_row, 30, f' FPS={1 / (time() - fps_time):6.2f} ')
        fps_time = time()
        canvas.refresh()
        sleep(TIC_TIMEOUT)
        rows_direction, columns_direction, space_pressed = read_controls(canvas)
        rocket_pos['row'] = min(
            max(1, rocket_pos['row'] + rows_direction * ROCKET_SPEED),
            max_row - rocket_height
        )
        rocket_pos['col'] = min(
            max(1, rocket_pos['col'] + columns_direction * ROCKET_SPEED),
            max_col - rocket_width
        )
        if space_pressed and rocket_pos['row'] > 2:
            coroutines.append(fire(canvas, rocket_pos['row'] - 1, rocket_pos['col'] + 2))


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
